"""AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks)

Self-contained PyTorch module and inference wrapper with automatic HuggingFace checkpoint loading.
Reference: Clova AI / SpeechAntiSpoofingBenchmarks.
"""

import os
import time
from typing import Dict, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from huggingface_hub import hf_hub_download

# Standard AASIST architecture configuration (ASVspoof 2019 LA)
AASIST_CONFIG = {
    "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
    "gat_dims": [64, 32],
    "pool_ratios": [0.5, 0.5, 0.5, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0],
    "first_conv": 3,
}

CUT_LENGTH = 64600  # ~4.04 sec at 16kHz
HF_MODEL_ID = "SpeechAntiSpoofingBenchmarks/AASIST"
HF_FILENAME = "AASIST.pth"


class CONV(nn.Module):
    @staticmethod
    def to_mel(hz):
        return 2595 * np.log10(1 + hz / 700)

    @staticmethod
    def to_hz(mel):
        return 700 * (10 ** (mel / 2595) - 1)

    def __init__(
        self,
        out_channels: int,
        kernel_size: int,
        sample_rate: int = 16000,
        in_channels: int = 1,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        bias: bool = False,
        groups: int = 1,
    ):
        super().__init__()
        if in_channels != 1:
            raise ValueError(f"SincConv requires in_channels=1, got {in_channels}")
        self.out_channels = out_channels
        self.kernel_size = kernel_size + 1 if kernel_size % 2 == 0 else kernel_size
        self.sample_rate = sample_rate
        self.stride = stride
        self.padding = padding
        self.dilation = dilation

        NFFT = 512
        f = int(self.sample_rate / 2) * np.linspace(0, 1, int(NFFT / 2) + 1)
        fmel = self.to_mel(f)
        fmelmax = np.max(fmel)
        fmelmin = np.min(fmel)
        filbandwidthsmel = np.linspace(fmelmin, fmelmax, self.out_channels + 1)
        filbandwidthsf = self.to_hz(filbandwidthsmel)

        self.mel = filbandwidthsf
        self.hsupp = torch.arange(-(self.kernel_size - 1) / 2, (self.kernel_size - 1) / 2 + 1)
        self.band_pass = torch.zeros(self.out_channels, self.kernel_size)
        for i in range(len(self.mel) - 1):
            fmin = self.mel[i]
            fmax = self.mel[i + 1]
            hHigh = (2 * fmax / self.sample_rate) * np.sinc(2 * fmax * self.hsupp / self.sample_rate)
            hLow = (2 * fmin / self.sample_rate) * np.sinc(2 * fmin * self.hsupp / self.sample_rate)
            hideal = hHigh - hLow
            self.band_pass[i, :] = torch.Tensor(np.hamming(self.kernel_size)) * torch.Tensor(hideal)

    def forward(self, x: torch.Tensor, mask: bool = False) -> torch.Tensor:
        band_pass_filter = self.band_pass.clone().to(x.device)
        filters = band_pass_filter.view(self.out_channels, 1, self.kernel_size)
        return F.conv1d(
            x, filters, stride=self.stride, padding=self.padding, dilation=self.dilation, bias=None, groups=1
        )


class ResidualBlock(nn.Module):
    def __init__(self, nb_filts, first: bool = False):
        super().__init__()
        self.first = first
        if not self.first:
            self.bn1 = nn.BatchNorm2d(num_features=nb_filts[0])
        self.conv1 = nn.Conv2d(
            in_channels=nb_filts[0], out_channels=nb_filts[1], kernel_size=(2, 3), padding=(1, 1), stride=1
        )
        self.selu = nn.SELU(inplace=True)
        self.bn2 = nn.BatchNorm2d(num_features=nb_filts[1])
        self.conv2 = nn.Conv2d(
            in_channels=nb_filts[1], out_channels=nb_filts[1], kernel_size=(2, 3), padding=(0, 1), stride=1
        )
        self.downsample = nb_filts[0] != nb_filts[1]
        if self.downsample:
            self.conv_downsample = nn.Conv2d(
                in_channels=nb_filts[0], out_channels=nb_filts[1], padding=(0, 1), kernel_size=(1, 3), stride=1
            )
        self.mp = nn.MaxPool2d((1, 3))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        if not self.first:
            out = self.bn1(x)
            out = self.selu(out)
        else:
            out = x
        out = self.conv1(out)
        out = self.bn2(out)
        out = self.selu(out)
        out = self.conv2(out)

        if self.downsample:
            identity = self.conv_downsample(identity)
        out += identity
        return self.mp(out)


class GraphAttentionLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, **kwargs):
        super().__init__()
        self.att_proj = nn.Linear(in_dim, out_dim)
        self.att_weight = nn.Parameter(torch.FloatTensor(out_dim, 1))
        nn.init.xavier_normal_(self.att_weight)
        self.proj_with_att = nn.Linear(in_dim, out_dim)
        self.proj_without_att = nn.Linear(in_dim, out_dim)
        self.bn = nn.BatchNorm1d(out_dim)
        self.input_drop = nn.Dropout(p=0.2)
        self.act = nn.SELU(inplace=True)
        self.temp = kwargs.get("temperature", 1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_drop(x)
        nb_nodes = x.size(1)
        x_pair = x.unsqueeze(2).expand(-1, -1, nb_nodes, -1) * x.unsqueeze(1).expand(-1, nb_nodes, -1, -1)
        att_map = torch.tanh(self.att_proj(x_pair))
        att_map = torch.matmul(att_map, self.att_weight) / self.temp
        att_map = F.softmax(att_map, dim=-2)

        x1 = self.proj_with_att(torch.matmul(att_map.squeeze(-1), x))
        x2 = self.proj_without_att(x)
        out = x1 + x2
        org_size = out.size()
        out = self.bn(out.view(-1, org_size[-1])).view(org_size)
        return self.act(out)


class HtrgGraphAttentionLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, **kwargs):
        super().__init__()
        self.proj_type1 = nn.Linear(in_dim, in_dim)
        self.proj_type2 = nn.Linear(in_dim, in_dim)
        self.att_proj = nn.Linear(in_dim, out_dim)
        self.att_projM = nn.Linear(in_dim, out_dim)

        self.att_weight11 = nn.Parameter(torch.FloatTensor(out_dim, 1))
        self.att_weight22 = nn.Parameter(torch.FloatTensor(out_dim, 1))
        self.att_weight12 = nn.Parameter(torch.FloatTensor(out_dim, 1))
        self.att_weightM = nn.Parameter(torch.FloatTensor(out_dim, 1))
        for w in [self.att_weight11, self.att_weight22, self.att_weight12, self.att_weightM]:
            nn.init.xavier_normal_(w)

        self.proj_with_att = nn.Linear(in_dim, out_dim)
        self.proj_without_att = nn.Linear(in_dim, out_dim)
        self.proj_with_attM = nn.Linear(in_dim, out_dim)
        self.proj_without_attM = nn.Linear(in_dim, out_dim)
        self.bn = nn.BatchNorm1d(out_dim)
        self.input_drop = nn.Dropout(p=0.2)
        self.act = nn.SELU(inplace=True)
        self.temp = kwargs.get("temperature", 1.0)

    def forward(
        self, x1: torch.Tensor, x2: torch.Tensor, master: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        num1 = x1.size(1)
        num2 = x2.size(1)
        x = torch.cat([self.proj_type1(x1), self.proj_type2(x2)], dim=1)
        if master is None:
            master = torch.mean(x, dim=1, keepdim=True)
        x = self.input_drop(x)

        nb_nodes = x.size(1)
        x_pair = x.unsqueeze(2).expand(-1, -1, nb_nodes, -1) * x.unsqueeze(1).expand(-1, nb_nodes, -1, -1)
        att_map = torch.tanh(self.att_proj(x_pair))
        att_board = torch.zeros_like(att_map[:, :, :, 0]).unsqueeze(-1)
        att_board[:, :num1, :num1, :] = torch.matmul(att_map[:, :num1, :num1, :], self.att_weight11)
        att_board[:, num1:, num1:, :] = torch.matmul(att_map[:, num1:, num1:, :], self.att_weight22)
        att_board[:, :num1, num1:, :] = torch.matmul(att_map[:, :num1, num1:, :], self.att_weight12)
        att_board[:, num1:, :num1, :] = torch.matmul(att_map[:, num1:, :num1, :], self.att_weight12)
        att_map = F.softmax(att_board / self.temp, dim=-2)

        att_master = F.softmax(torch.matmul(torch.tanh(self.att_projM(x * master)), self.att_weightM) / self.temp, dim=-2)
        master = self.proj_with_attM(torch.matmul(att_master.squeeze(-1).unsqueeze(1), x)) + self.proj_without_attM(master)

        out = self.proj_with_att(torch.matmul(att_map.squeeze(-1), x)) + self.proj_without_att(x)
        org_size = out.size()
        out = self.act(self.bn(out.view(-1, org_size[-1])).view(org_size))
        return out.narrow(1, 0, num1), out.narrow(1, num1, num2), master


class GraphPool(nn.Module):
    def __init__(self, k: float, in_dim: int, p: float = 0.3):
        super().__init__()
        self.k = k
        self.proj = nn.Linear(in_dim, 1)
        self.drop = nn.Dropout(p=p) if p > 0 else nn.Identity()

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        scores = torch.sigmoid(self.proj(self.drop(h)))
        n_nodes = max(int(h.size(1) * self.k), 1)
        _, idx = torch.topk(scores, n_nodes, dim=1)
        idx = idx.expand(-1, -1, h.size(2))
        return torch.gather(h * scores, 1, idx)


class AASISTModel(nn.Module):
    def __init__(self, d_args: dict = AASIST_CONFIG):
        super().__init__()
        filts = d_args["filts"]
        gat_dims = d_args["gat_dims"]
        pool_ratios = d_args["pool_ratios"]
        temperatures = d_args["temperatures"]

        self.conv_time = CONV(out_channels=filts[0], kernel_size=d_args["first_conv"], in_channels=1)
        self.first_bn = nn.BatchNorm2d(num_features=1)
        self.drop = nn.Dropout(0.5, inplace=True)
        self.drop_way = nn.Dropout(0.2, inplace=True)
        self.selu = nn.SELU(inplace=True)

        self.encoder = nn.Sequential(
            nn.Sequential(ResidualBlock(nb_filts=filts[1], first=True)),
            nn.Sequential(ResidualBlock(nb_filts=filts[2])),
            nn.Sequential(ResidualBlock(nb_filts=filts[3])),
            nn.Sequential(ResidualBlock(nb_filts=filts[4])),
            nn.Sequential(ResidualBlock(nb_filts=filts[4])),
            nn.Sequential(ResidualBlock(nb_filts=filts[4])),
        )

        self.pos_S = nn.Parameter(torch.randn(1, 23, filts[-1][-1]))
        self.master1 = nn.Parameter(torch.randn(1, 1, gat_dims[0]))
        self.master2 = nn.Parameter(torch.randn(1, 1, gat_dims[0]))

        self.GAT_layer_S = GraphAttentionLayer(filts[-1][-1], gat_dims[0], temperature=temperatures[0])
        self.GAT_layer_T = GraphAttentionLayer(filts[-1][-1], gat_dims[0], temperature=temperatures[1])
        self.HtrgGAT_layer_ST11 = HtrgGraphAttentionLayer(gat_dims[0], gat_dims[1], temperature=temperatures[2])
        self.HtrgGAT_layer_ST12 = HtrgGraphAttentionLayer(gat_dims[1], gat_dims[1], temperature=temperatures[2])
        self.HtrgGAT_layer_ST21 = HtrgGraphAttentionLayer(gat_dims[0], gat_dims[1], temperature=temperatures[2])
        self.HtrgGAT_layer_ST22 = HtrgGraphAttentionLayer(gat_dims[1], gat_dims[1], temperature=temperatures[2])

        self.pool_S = GraphPool(pool_ratios[0], gat_dims[0], 0.3)
        self.pool_T = GraphPool(pool_ratios[1], gat_dims[0], 0.3)
        self.pool_hS1 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)
        self.pool_hT1 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)
        self.pool_hS2 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)
        self.pool_hT2 = GraphPool(pool_ratios[2], gat_dims[1], 0.3)

        self.out_layer = nn.Linear(5 * gat_dims[1], 2)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        x = x.unsqueeze(1)
        x = self.conv_time(x)
        x = x.unsqueeze(dim=1)
        x = F.max_pool2d(torch.abs(x), (3, 3))
        x = self.selu(self.first_bn(x))

        e = self.encoder(x)
        e_S, _ = torch.max(torch.abs(e), dim=3)
        e_S = e_S.transpose(1, 2) + self.pos_S
        gat_S = self.GAT_layer_S(e_S)
        out_S = self.pool_S(gat_S)

        e_T, _ = torch.max(torch.abs(e), dim=2)
        e_T = e_T.transpose(1, 2)
        gat_T = self.GAT_layer_T(e_T)
        out_T = self.pool_T(gat_T)

        out_T1, out_S1, master1 = self.HtrgGAT_layer_ST11(out_T, out_S, master=self.master1)
        out_S1 = self.pool_hS1(out_S1)
        out_T1 = self.pool_hT1(out_T1)
        out_T_aug, out_S_aug, master_aug = self.HtrgGAT_layer_ST12(out_T1, out_S1, master=master1)
        out_T1 = out_T1 + out_T_aug
        out_S1 = out_S1 + out_S_aug
        master1 = master1 + master_aug

        out_T2, out_S2, master2 = self.HtrgGAT_layer_ST21(out_T, out_S, master=self.master2)
        out_S2 = self.pool_hS2(out_S2)
        out_T2 = self.pool_hT2(out_T2)
        out_T_aug2, out_S_aug2, master_aug2 = self.HtrgGAT_layer_ST22(out_T2, out_S2, master=master2)
        out_T2 = out_T2 + out_T_aug2
        out_S2 = out_S2 + out_S_aug2
        master2 = master2 + master_aug2

        out_T = torch.max(self.drop_way(out_T1), self.drop_way(out_T2))
        out_S = torch.max(self.drop_way(out_S1), self.drop_way(out_S2))
        master = torch.max(self.drop_way(master1), self.drop_way(master2))

        T_max, _ = torch.max(torch.abs(out_T), dim=1)
        T_avg = torch.mean(out_T, dim=1)
        S_max, _ = torch.max(torch.abs(out_S), dim=1)
        S_avg = torch.mean(out_S, dim=1)

        last_hidden = self.drop(torch.cat([T_max, T_avg, S_max, S_avg, master.squeeze(1)], dim=1))
        output = self.out_layer(last_hidden)
        return last_hidden, output


class AASISTInferencer:
    """Production wrapper for AASIST inference and VRAM/latency tracking."""

    def __init__(self, device: Optional[torch.device] = None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model: Optional[AASISTModel] = None

    def load_weights(self, cache_dir: Optional[str] = None):
        """Downloads or loads pretrained weights from HuggingFace."""
        ckpt_path = hf_hub_download(repo_id=HF_MODEL_ID, filename=HF_FILENAME, cache_dir=cache_dir)
        self.model = AASISTModel(AASIST_CONFIG)
        state_dict = torch.load(ckpt_path, map_location=self.device, weights_only=True)
        if "model" in state_dict:
            state_dict = state_dict["model"]
        self.model.load_state_dict(state_dict, strict=True)
        self.model.to(self.device)
        self.model.eval()

    def score_audio(self, waveform: torch.Tensor) -> Dict:
        """Processes 16kHz audio and outputs spoof score and performance metrics.

        waveform: Tensor of shape (samples,) or (1, samples)
        """
        if self.model is None:
            self.load_weights()

        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)

        # Pad or crop to 64600 samples
        samples = waveform.size(1)
        if samples < CUT_LENGTH:
            repeats = int(np.ceil(CUT_LENGTH / samples))
            inp = waveform.repeat(1, repeats)[:, :CUT_LENGTH]
        else:
            inp = waveform[:, :CUT_LENGTH]

        inp = inp.to(self.device)

        if self.device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(self.device)
            torch.cuda.synchronize(self.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            _, logits = self.model(inp)
            probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()

        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
            peak_vram_mb = torch.cuda.max_memory_allocated(self.device) / (1024 * 1024)
        else:
            peak_vram_mb = 0.0

        latency_ms = (time.perf_counter() - t0) * 1000

        spoof_logit = float(logits[0, 0].item())
        bona_fide_logit = float(logits[0, 1].item())
        bona_fide_prob = float(probs[1])

        # SASV convention: positive score = more bona fide, negative = spoof
        cm_score = bona_fide_logit - spoof_logit

        return {
            "cm_score": round(cm_score, 4),
            "bona_fide_logit": round(bona_fide_logit, 4),
            "spoof_logit": round(spoof_logit, 4),
            "bona_fide_prob": round(bona_fide_prob, 4),
            "predicted_label": "bona_fide" if bona_fide_logit > spoof_logit else "spoof",
            "latency_ms": round(latency_ms, 2),
            "peak_vram_mb": round(peak_vram_mb, 2),
            "device": str(self.device),
        }

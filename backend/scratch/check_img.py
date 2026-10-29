from PIL import Image

for name in ["slide_3_img_1_Image 0.png", "slide_9_img_1_Image 0.jpg"]:
    img = Image.open(f"scratch/extracted_images/{name}")
    print(f"{name}: size={img.size}, format={img.format}, mode={img.mode}")

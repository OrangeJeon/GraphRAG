from PIL import Image
import os

folder = r"C:\python\Graph_RAG\진천군수도정비기본계획보고서(2021)_images"
for f in os.listdir(folder):
    img = Image.open(f"{folder}/{f}")
    size = os.path.getsize(f"{folder}/{f}")
    print(f"{f}: {img.width}x{img.height}px, {size//1024}KB")
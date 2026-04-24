from PIL import Image, ImageDraw

def create_icon():
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    draw.ellipse([20, 20, 236, 236], fill=(66, 133, 244, 255), outline=(33, 66, 133, 255), width=8)
    
    # 食指
    draw.polygon([(128, 60), (118, 100), (138, 100)], fill=(255, 255, 255, 255))
    # 中指
    draw.polygon([(145, 70), (155, 120), (175, 120)], fill=(255, 255, 255, 255))
    # 无名指
    draw.polygon([(172, 80), (182, 130), (202, 130)], fill=(255, 255, 255, 255))
    # 小指
    draw.polygon([(199, 95), (209, 145), (229, 145)], fill=(255, 255, 255, 255))
    
    # 手掌
    draw.ellipse([80, 120, 176, 200], fill=(255, 255, 255, 255))
    
    # 大拇指
    draw.polygon([(60, 140), (80, 160), (90, 140)], fill=(255, 255, 255, 255))
    
    # 鼠标指针
    draw.polygon([(170, 170), (170, 210), (185, 195), (200, 220), (205, 215), (190, 190), (210, 190)], 
                 fill=(51, 51, 51, 255))
    
    return img

def create_icon_ico():
    icon = create_icon()
    icon.save(r'c:\Users\fanfan\Desktop\CvApplication\AiVirtualMouse\mouse_icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("图标已创建: mouse_icon.ico")

if __name__ == "__main__":
    create_icon_ico()

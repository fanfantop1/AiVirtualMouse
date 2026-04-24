import cv2
import HandTrackingModule as htm
import autopy
import numpy as np
import time
import pyautogui
import os
from PIL import Image, ImageDraw, ImageFont

##############################
wCam, hCam = 240, 180  # 进一步降低分辨率
frameR = 30  # 减小边框大小，放大绿色框
smoothening = 5  # 减少平滑处理的计算量
skip_frames = 2  # 每隔几帧检测一次手部
##############################

# 方向映射：0-360度，对应不同的方向
direction_offset = 0  # 默认0度，手指向上对应屏幕向上
show_direction_control = False  # 是否显示方向控制
frame_count = 0  # 帧计数器
last_lmList = []  # 上一帧的手部关键点
has_hand = False  # 上一帧是否检测到手部
frame_size_scale = 1.0  # 框大小的缩放比例（1.0是默认大小）
frame_offset_x = 0  # 框的水平偏移
frame_offset_y = 0  # 框的垂直偏移
confidence_threshold = 0.5  # 置信度阈值（0-1之间）

# 置信度阈值更新标志
confidence_changed = False

# 教程显示状态
show_tutorial = False

# 窗口是否已创建标志
window_created = False

# 查找中文字体
def get_chinese_font():
    """查找系统中的中文字体"""
    # 尝试常见的中文字体路径
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
        "C:/Windows/Fonts/msyh.ttf",    # 微软雅黑
        "C:/Windows/Fonts/msyhbd.ttf",  # 微软雅黑 Bold
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            return font_path
    return None

# 获取中文字体路径
chinese_font = get_chinese_font()

def draw_chinese_text(img, text, position, font_size=20, color=(255, 255, 255)):
    """绘制中文字符"""
    if chinese_font:
        try:
            # 仅在需要时创建字体对象
            font = ImageFont.truetype(chinese_font, font_size)
            # 转换为 PIL 图像
            img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(img_pil)
            # 绘制文本
            draw.text(position, text, font=font, fill=color)
            # 转换回 OpenCV 格式
            img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        except Exception as e:
            # 出错时使用默认字体
            cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    else:
        # 如果没有中文字体，使用默认字体
        cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return img
cap = cv2.VideoCapture(0)  # 若使用笔记本自带摄像头则编号为0  若使用外接摄像头 则更改为1或其他编号
cap.set(3, wCam)
cap.set(4, hCam)
pTime = 0
plocX, plocY = 0, 0
clocX, clocY = 0, 0

# 优化检测参数，提高性能
detector = htm.handDetector(mode=False, maxHands=1, modelComplexity=0, detectionCon=confidence_threshold, trackCon=confidence_threshold)
wScr, hScr = autopy.screen.size()
# print(wScr, hScr)

def draw_direction_control(img):
    """绘制方向控制界面"""
    # 绘制圆形滑块
    center = (wCam // 2, hCam // 2)
    radius = 100
    
    # 绘制外圈
    cv2.circle(img, center, radius, (255, 255, 255), 2)
    cv2.circle(img, center, radius - 5, (200, 200, 200), 1)
    
    # 绘制方向指示器
    angle_rad = np.deg2rad(direction_offset)
    indicator_x = center[0] + int(np.sin(angle_rad) * (radius - 20))
    indicator_y = center[1] - int(np.cos(angle_rad) * (radius - 20))
    cv2.line(img, center, (indicator_x, indicator_y), (0, 255, 0), 3)
    cv2.circle(img, (indicator_x, indicator_y), 10, (0, 255, 0), cv2.FILLED)
    
    # 绘制方向文本
    directions = ['上', '右', '下', '左']
    for i, direction in enumerate(directions):
        angle = i * 90
        text_x = center[0] + int(np.sin(np.deg2rad(angle)) * (radius + 30))
        text_y = center[1] - int(np.cos(np.deg2rad(angle)) * (radius + 30))
        img = draw_chinese_text(img, direction, (text_x - 10, text_y - 10), 20, (255, 255, 255))
    
    # 绘制操作提示
    img = draw_chinese_text(img, '鼠标点击调整方向', (50, hCam - 50), 16, (255, 255, 255))
    img = draw_chinese_text(img, '按 E 键退出方向调整', (50, hCam - 25), 16, (255, 255, 255))
    
    return img

def draw_tutorial(img):
    """绘制使用教程界面"""
    # 半透明背景
    overlay = img.copy()
    cv2.rectangle(overlay, (10, 10), (wCam - 10, hCam - 10), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.8, img, 0.2, 0, img)
    
    # 标题
    img = draw_chinese_text(img, '使用教程', (wCam // 2 - 40, 30), 18, (0, 255, 255))
    
    # 教程内容
    tutorials = [
        '手势操作:',
        '  食指伸出 - 移动鼠标',
        '  食指+中指靠近 - 点击鼠标',
        '  中指伸出 - 向上滚动',
        '  小指伸出 - 向下滚动',
        '',
        '快捷键:',
        '  Q - 调整方向',
        '  +/- - 调整框大小',
        '  WASD/方向键 - 移动框',
        '  Z/X - 调整置信度',
        '  H - 显示/隐藏教程',
        '  ESC - 关闭软件',
    ]
    
    y_pos = 55
    for line in tutorials:
        img = draw_chinese_text(img, line, (20, y_pos), 12, (255, 255, 255))
        y_pos += 15
    
    # 关闭提示
    img = draw_chinese_text(img, '按 H 或点击关闭', (wCam // 2 - 50, hCam - 25), 12, (255, 255, 0))
    
    return img

def calculate_angle(x, y, center):
    """计算点相对于中心的角度"""
    dx = x - center[0]
    dy = center[1] - y
    angle = np.degrees(np.arctan2(dx, dy))
    if angle < 0:
        angle += 360
    return angle

# 创建窗口并设置位置
cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
cv2.moveWindow("Image", 100, 100)
cv2.resizeWindow("Image", wCam * 3, hCam * 3)  # 放大窗口显示

while True:
    success, img = cap.read()
    if not success:
        continue
    
    # 计算框位置（在最小化检测之前）
    margin = 20
    half_width = wCam // 2
    quarter_height = hCam // 4
    
    original_frame_width = (wCam - margin) - (half_width + margin)
    original_frame_height = (hCam - quarter_height) - quarter_height
    
    new_frame_width = int(original_frame_width * frame_size_scale)
    new_frame_height = int(original_frame_height * frame_size_scale)
    
    center_x = (half_width + margin + wCam - margin) // 2 + frame_offset_x
    center_y = (quarter_height + hCam - quarter_height) // 2 + frame_offset_y
    
    frame_left = center_x - new_frame_width // 2
    frame_right = center_x + new_frame_width // 2
    frame_top = center_y - new_frame_height // 2
    frame_bottom = center_y + new_frame_height // 2
    
    # 检测窗口是否最小化
    try:
        if window_created:
            window_visible = cv2.getWindowProperty("Image", cv2.WND_PROP_VISIBLE) >= 1
        else:
            window_visible = True  # 第一次运行时假设窗口可见
    except:
        window_visible = False
    
    # 如果窗口最小化，只进行手部检测和鼠标控制，跳过图像显示
    if not window_visible:
        # 如果置信度阈值改变，重新初始化detector
        if confidence_changed:
            detector = htm.handDetector(mode=False, maxHands=1, modelComplexity=0, detectionCon=confidence_threshold, trackCon=confidence_threshold)
            confidence_changed = False
        
        frame_count += 1
        should_detect = frame_count % skip_frames == 0
        
        # 检测手部
        if should_detect:
            # 最小化模式下，不绘制手部，只进行检测
            lmList = detector.findPosition(img, draw=False)
            has_hand = len(lmList) != 0
            if has_hand:
                last_lmList = lmList.copy()
        else:
            if has_hand:
                lmList = last_lmList
            else:
                lmList = []
        
        # 手势控制
        if len(lmList) != 0:
            x1, y1 = lmList[8][1:]
            x2, y2 = lmList[12][1:]
            fingers = detector.fingersUp()
            
            if fingers[1] and fingers[2] == False:
                x3 = np.interp(x1, (frame_left, frame_right), (0, wScr))
                y3 = np.interp(y1, (frame_top, frame_bottom), (0, hScr))
                
                if direction_offset != 0:
                    screen_center_x, screen_center_y = wScr // 2, hScr // 2
                    rel_x, rel_y = x3 - screen_center_x, y3 - screen_center_y
                    angle_rad = np.deg2rad(direction_offset)
                    cos_a = np.cos(angle_rad)
                    sin_a = np.sin(angle_rad)
                    rotated_x = rel_x * cos_a - rel_y * sin_a
                    rotated_y = rel_x * sin_a + rel_y * cos_a
                    x3_rotated = rotated_x + screen_center_x
                    y3_rotated = rotated_y + screen_center_y
                else:
                    x3_rotated = x3
                    y3_rotated = y3
                
                clocX = plocX + (x3_rotated - plocX) / smoothening
                clocY = plocY + (y3_rotated - plocY) / smoothening
                
                if abs(clocX - plocX) > 1 or abs(clocY - plocY) > 1:
                    autopy.mouse.move(wScr - clocX, clocY)
                plocX, plocY = clocX, clocY
            
            if fingers[1] and fingers[2]:
                # 最小化模式下，不计算距离（避免绘制）
                # 直接使用固定距离判断
                autopy.mouse.click()
            
            if fingers[2]:
                pyautogui.scroll(300)
            if fingers[4]:
                pyautogui.scroll(-300)
        
        # 检查窗口是否恢复
        key = cv2.waitKey(5)  # 增加等待时间，减少CPU占用
        if key == 27:
            break
        continue
    
    # 如果置信度阈值改变，重新初始化detector
    if confidence_changed:
        detector = htm.handDetector(mode=False, maxHands=1, modelComplexity=0, detectionCon=confidence_threshold, trackCon=confidence_threshold)
        confidence_changed = False
    
    frame_count += 1
    should_detect = frame_count % skip_frames == 0
    
    # 1. 检测手部 得到手指关键点坐标
    # 每隔几帧检测一次，提高帧率
    if should_detect:
        img = detector.findHands(img)
        lmList = detector.findPosition(img, draw=False)
        has_hand = len(lmList) != 0
        if has_hand:
            last_lmList = lmList.copy()
    else:
        # 使用上一帧的检测结果
        if has_hand:
            lmList = last_lmList
        else:
            lmList = []
    
    # 绘制绿色框
    cv2.rectangle(img, (frame_left, frame_top), (frame_right, frame_bottom), (0, 255, 0), 2,  cv2.FONT_HERSHEY_PLAIN)

    # 2. 判断食指和中指是否伸出
    if len(lmList) != 0:
        x1, y1 = lmList[8][1:]
        x2, y2 = lmList[12][1:]
        fingers = detector.fingersUp()

        # 3. 若只有食指伸出 则进入移动模式
        if fingers[1] and fingers[2] == False:
            # 4. 坐标转换： 将食指在窗口坐标转换为鼠标在桌面的坐标
            # 鼠标坐标
            x3 = np.interp(x1, (frame_left, frame_right), (0, wScr))
            y3 = np.interp(y1, (frame_top, frame_bottom), (0, hScr))

            # 应用方向偏移
            if direction_offset != 0:
                # 只在有方向偏移时进行旋转计算
                screen_center_x, screen_center_y = wScr // 2, hScr // 2
                rel_x, rel_y = x3 - screen_center_x, y3 - screen_center_y
                
                # 旋转坐标
                angle_rad = np.deg2rad(direction_offset)
                cos_a = np.cos(angle_rad)
                sin_a = np.sin(angle_rad)
                rotated_x = rel_x * cos_a - rel_y * sin_a
                rotated_y = rel_x * sin_a + rel_y * cos_a
                
                # 转换回屏幕坐标
                x3_rotated = rotated_x + screen_center_x
                y3_rotated = rotated_y + screen_center_y
            else:
                # 无方向偏移时直接使用原始坐标
                x3_rotated = x3
                y3_rotated = y3

            # smoothening values
            clocX = plocX + (x3_rotated - plocX) / smoothening
            clocY = plocY + (y3_rotated - plocY) / smoothening

            # 只在鼠标位置变化较大时才移动
            if abs(clocX - plocX) > 1 or abs(clocY - plocY) > 1:
                autopy.mouse.move(wScr - clocX, clocY)
            cv2.circle(img, (x1, y1), 15, (255, 0, 255), cv2.FILLED)
            plocX, plocY = clocX, clocY

        # 5. 若是食指和中指都伸出 则检测指头距离 距离够短则对应鼠标点击
        if fingers[1] and fingers[2]:
            length, img, pointInfo = detector.findDistance(8, 12, img)
            if length < 40:
                cv2.circle(img, (pointInfo[4], pointInfo[5]),
                           15, (0, 255, 0), cv2.FILLED)
                autopy.mouse.click()

        if fingers[2]:
            pyautogui.scroll(300)
        if fingers[4]:
            pyautogui.scroll(-300)




    # 方向控制模式
    if show_direction_control:
        img = draw_direction_control(img)
        cv2.imshow("Image", img)
        window_created = True  # 标记窗口已创建
        key = cv2.waitKey(1)
        
        # 鼠标点击事件
        def mouse_callback(event, x, y, flags, param):
            global direction_offset
            if event == cv2.EVENT_LBUTTONDOWN:
                center = (wCam // 2, hCam // 2)
                direction_offset = calculate_angle(x, y, center)
                print(f"方向调整为: {direction_offset:.1f}度")
        
        cv2.setMouseCallback("Image", mouse_callback)
        
        if key == ord('e') or key == ord('E'):
            show_direction_control = False
            print("退出方向调整模式")
        elif key == 27:  # Esc 键
            break
        continue
    
    cTime = time.time()
    fps = 1 / (cTime - pTime)
    pTime = cTime
    
    # 显示 FPS
    cv2.putText(img, f'fps:{int(fps)}', [15, 25],
                cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)
    
    # 左上角显示 "esc关闭"
    img = draw_chinese_text(img, 'esc关闭', (15, hCam - 15), 20, (0, 255, 0))
    
    # 右上角显示 "Made by fanfan"
    cv2.putText(img, 'Made by fanfan', (wCam - 150, 25),
                cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)
    
    # 显示方向调整提示
    img = draw_chinese_text(img, '按 Q 键调整方向', (15, hCam - 45), 16, (255, 255, 0))
    
    # 显示框大小调整提示
    img = draw_chinese_text(img, '按 + 放大框 按 - 缩小框', (15, hCam - 70), 14, (255, 255, 0))
    
    # 显示框位置调整提示
    img = draw_chinese_text(img, '方向键或WASD移动框', (15, hCam - 90), 12, (255, 255, 0))
    
    # 显示置信度阈值
    img = draw_chinese_text(img, f'置信度: {confidence_threshold:.2f}  Z降低 X提高', (15, hCam - 110), 11, (255, 255, 0))
    
    # 绘制教程按钮
    button_x, button_y = wCam - 70, hCam - 30
    button_w, button_h = 60, 25
    cv2.rectangle(img, (button_x, button_y), (button_x + button_w, button_y + button_h), (100, 100, 255), -1)
    cv2.rectangle(img, (button_x, button_y), (button_x + button_w, button_y + button_h), (255, 255, 255), 2)
    img = draw_chinese_text(img, '教程', (button_x + 15, button_y + 20), 16, (255, 255, 255))
    
    # 如果显示教程，绘制教程界面
    if show_tutorial:
        img = draw_tutorial(img)
    
    cv2.imshow("Image", img)
    window_created = True  # 标记窗口已创建
    
    # 鼠标点击事件
    def mouse_callback(event, x, y, flags, param):
        global show_tutorial
        if event == cv2.EVENT_LBUTTONDOWN:
            # 检测教程按钮点击
            if button_x <= x <= button_x + button_w and button_y <= y <= button_y + button_h:
                show_tutorial = not show_tutorial
                print(f"教程显示: {'开启' if show_tutorial else '关闭'}")
            # 如果教程显示中，点击任意位置关闭教程
            elif show_tutorial:
                show_tutorial = False
                print("教程显示: 关闭")
    
    cv2.setMouseCallback("Image", mouse_callback)
    
    key = cv2.waitKey(1)
    if key == 27:  # Esc 键
        break
    elif key == ord('q') or key == ord('Q'):
        show_direction_control = True
        print("进入方向调整模式")
    elif key == ord('+') or key == ord('='):
        # 放大框
        frame_size_scale = min(frame_size_scale + 0.1, 2.0)
        print(f"框大小放大为: {frame_size_scale:.1f}")
    elif key == ord('-') or key == ord('_'):
        # 缩小框
        frame_size_scale = max(frame_size_scale - 0.1, 0.3)
        print(f"框大小缩小为: {frame_size_scale:.1f}")
    elif key == 81 or key == 2424832 or key == ord('a') or key == ord('A'):  # 左箭头键或A键
        frame_offset_x -= 5
        print(f"框左移，X偏移: {frame_offset_x}")
    elif key == 83 or key == 2555904 or key == ord('d') or key == ord('D'):  # 右箭头键或D键
        frame_offset_x += 5
        print(f"框右移，X偏移: {frame_offset_x}")
    elif key == 82 or key == 2490368 or key == ord('w') or key == ord('W'):  # 上箭头键或W键
        frame_offset_y -= 5
        print(f"框上移，Y偏移: {frame_offset_y}")
    elif key == 84 or key == 2621440 or key == ord('s') or key == ord('S'):  # 下箭头键或S键
        frame_offset_y += 5
        print(f"框下移，Y偏移: {frame_offset_y}")
    elif key == ord('z') or key == ord('Z'):  # Z键降低置信度
        confidence_threshold = max(confidence_threshold - 0.05, 0.1)
        confidence_changed = True
        print(f"置信度降低为: {confidence_threshold:.2f}")
    elif key == ord('x') or key == ord('X'):  # X键提高置信度
        confidence_threshold = min(confidence_threshold + 0.05, 0.95)
        confidence_changed = True
        print(f"置信度提高为: {confidence_threshold:.2f}")
    elif key == ord('h') or key == ord('H'):  # H键切换教程显示
        show_tutorial = not show_tutorial
        print(f"教程显示: {'开启' if show_tutorial else '关闭'}")

# 释放资源
cap.release()
cv2.destroyAllWindows()
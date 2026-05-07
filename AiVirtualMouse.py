import cv2
import HandTrackingModule as htm
import autopy
import numpy as np
import time
import pyautogui
import os
import json
from PIL import Image, ImageDraw, ImageFont

##############################
wCam, hCam = 240, 180
frameR = 30
smoothening = 5
skip_frames = 2
##############################

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# ---- 状态变量 ----
direction_offset = 0
show_direction_control = False
frame_count = 0
last_lmList = []
has_hand = False
frame_size_scale = 1.0
frame_offset_x = 0
frame_offset_y = 0
confidence_threshold = 0.5
confidence_changed = False
show_tutorial = False
window_created = False

# 教程按钮位置（基于常量，只算一次）
button_x, button_y = wCam - 70, hCam - 30
button_w, button_h = 60, 25

# ---- 文本渲染缓存 ----
_text_cache = {}

# ---- 配置持久化 ----

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config():
    config = {
        "direction_offset": direction_offset,
        "frame_size_scale": frame_size_scale,
        "frame_offset_x": frame_offset_x,
        "frame_offset_y": frame_offset_y,
        "confidence_threshold": confidence_threshold,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass

def apply_config(cfg):
    global direction_offset, frame_size_scale, frame_offset_x, frame_offset_y, confidence_threshold
    direction_offset = cfg.get("direction_offset", 0)
    frame_size_scale = cfg.get("frame_size_scale", 1.0)
    frame_offset_x = cfg.get("frame_offset_x", 0)
    frame_offset_y = cfg.get("frame_offset_y", 0)
    confidence_threshold = cfg.get("confidence_threshold", 0.5)

apply_config(load_config())

# ---- 中文字体 ----

def get_chinese_font():
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttf",
        "C:/Windows/Fonts/msyhbd.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return fp
    return None

chinese_font = get_chinese_font()

def render_chinese_text(text, font_size=20, color=(255, 255, 255)):
    """将中文渲染为小尺寸 numpy 图像（带缓存），返回 RGBA 数组或 None"""
    if not chinese_font:
        return None
    cache_key = (text, font_size, color)
    if cache_key in _text_cache:
        return _text_cache[cache_key]
    font = ImageFont.truetype(chinese_font, font_size)
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if tw <= 0 or th <= 0:
        _text_cache[cache_key] = None
        return None
    txt_img = Image.new("RGBA", (tw + 4, th + 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_img)
    draw.text((2 - bbox[0], 2 - bbox[1]), text, font=font, fill=color)
    arr = np.array(txt_img)
    _text_cache[cache_key] = arr
    return arr

def draw_chinese_text(img, text, position, font_size=20, color=(255, 255, 255)):
    """在 OpenCV 图像上绘制中文（使用缓存避免每帧 PIL 转换）"""
    rendered = render_chinese_text(text, font_size, color)
    if rendered is None:
        cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        return img
    px, py = position
    rh, rw = rendered.shape[:2]
    if py + rh > img.shape[0] or px + rw > img.shape[1]:
        return img
    alpha = rendered[:, :, 3:] / 255.0
    roi = img[py:py + rh, px:px + rw]
    blended = (1 - alpha) * roi + alpha * rendered[:, :, :3]
    img[py:py + rh, px:px + rw] = blended.astype(np.uint8)
    return img

# ---- 辅助函数 ----

def rotate_coordinates(x, y, screen_w, screen_h, angle_deg):
    """将屏幕坐标按给定角度绕屏幕中心旋转"""
    if angle_deg == 0:
        return x, y
    cx, cy = screen_w // 2, screen_h // 2
    rad = np.deg2rad(angle_deg)
    rel_x, rel_y = x - cx, y - cy
    rot_x = rel_x * np.cos(rad) - rel_y * np.sin(rad)
    rot_y = rel_x * np.sin(rad) + rel_y * np.cos(rad)
    return rot_x + cx, rot_y + cy

def calculate_angle(x, y, center):
    dx = x - center[0]
    dy = center[1] - y
    angle = np.degrees(np.arctan2(dx, dy))
    if angle < 0:
        angle += 360
    return angle

def process_gestures(lmList, detector, frame_box, screen_size, angle, ploc, smooth):
    """
    统一的手势处理。返回 (clocX, clocY, should_click, scroll_delta)。
    - clocX/clocY: 平滑后的鼠标位置
    - should_click: 是否触发点击
    - scroll_delta: >0 上滚, <0 下滚, 0 不滚
    """
    clocX, clocY = ploc
    should_click = False
    scroll_delta = 0

    if len(lmList) == 0:
        return clocX, clocY, should_click, scroll_delta

    x1, y1 = lmList[8][1:]
    fingers = detector.fingersUp()
    fL, fT, fR, fB = frame_box
    wScr, hScr = screen_size

    # 移动模式：仅食指伸出
    if fingers[1] and not fingers[2]:
        x3 = np.interp(x1, (fL, fR), (0, wScr))
        y3 = np.interp(y1, (fT, fB), (0, hScr))
        x3, y3 = rotate_coordinates(x3, y3, wScr, hScr, angle)
        clocX = ploc[0] + (x3 - ploc[0]) / smooth
        clocY = ploc[1] + (y3 - ploc[1]) / smooth

    # 点击：食指+中指伸出
    if fingers[1] and fingers[2]:
        should_click = True

    # 滚轮
    if fingers[2]:
        scroll_delta = 300
    if fingers[4]:
        scroll_delta = -300

    return clocX, clocY, should_click, scroll_delta

def init_detector():
    return htm.handDetector(
        mode=False, maxHands=1, modelComplexity=0,
        detectionCon=confidence_threshold, trackCon=confidence_threshold
    )

def draw_direction_control(img):
    center = (wCam // 2, hCam // 2)
    radius = 100
    cv2.circle(img, center, radius, (255, 255, 255), 2)
    cv2.circle(img, center, radius - 5, (200, 200, 200), 1)
    angle_rad = np.deg2rad(direction_offset)
    ix = center[0] + int(np.sin(angle_rad) * (radius - 20))
    iy = center[1] - int(np.cos(angle_rad) * (radius - 20))
    cv2.line(img, center, (ix, iy), (0, 255, 0), 3)
    cv2.circle(img, (ix, iy), 10, (0, 255, 0), cv2.FILLED)
    directions = ['上', '右', '下', '左']
    for i, d in enumerate(directions):
        a = i * 90
        tx = center[0] + int(np.sin(np.deg2rad(a)) * (radius + 30))
        ty = center[1] - int(np.cos(np.deg2rad(a)) * (radius + 30))
        img = draw_chinese_text(img, d, (tx - 10, ty - 10), 20, (255, 255, 255))
    img = draw_chinese_text(img, '鼠标点击调整方向', (50, hCam - 50), 16, (255, 255, 255))
    img = draw_chinese_text(img, '按 E 键退出方向调整', (50, hCam - 25), 16, (255, 255, 255))
    return img

def draw_tutorial(img):
    overlay = img.copy()
    cv2.rectangle(overlay, (10, 10), (wCam - 10, hCam - 10), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.8, img, 0.2, 0, img)
    img = draw_chinese_text(img, '使用教程', (wCam // 2 - 40, 30), 18, (0, 255, 255))
    lines = [
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
    for line in lines:
        img = draw_chinese_text(img, line, (20, y_pos), 12, (255, 255, 255))
        y_pos += 15
    img = draw_chinese_text(img, '按 H 或点击关闭', (wCam // 2 - 50, hCam - 25), 12, (255, 255, 0))
    return img

# ---- 统一的鼠标回调（模块级别，只注册一次） ----

def on_mouse(event, x, y, flags, param):
    global direction_offset, show_tutorial
    if event == cv2.EVENT_LBUTTONDOWN:
        if show_direction_control:
            center = (wCam // 2, hCam // 2)
            direction_offset = calculate_angle(x, y, center)
            print(f"方向调整为: {direction_offset:.1f}度")
        else:
            if button_x <= x <= button_x + button_w and button_y <= y <= button_y + button_h:
                show_tutorial = not show_tutorial
                print(f"教程显示: {'开启' if show_tutorial else '关闭'}")
            elif show_tutorial:
                show_tutorial = False
                print("教程显示: 关闭")

# ---- 主程序 ----

cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)
pTime = 0
plocX, plocY = 0, 0

detector = init_detector()
wScr, hScr = autopy.screen.size()

cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
cv2.moveWindow("Image", 100, 100)
cv2.resizeWindow("Image", wCam * 3, hCam * 3)
cv2.setMouseCallback("Image", on_mouse)

while True:
    success, img = cap.read()
    if not success:
        continue

    # 计算绿色框位置
    margin = 20
    half_width = wCam // 2
    quarter_height = hCam // 4

    orig_fw = (wCam - margin) - (half_width + margin)
    orig_fh = (hCam - quarter_height) - quarter_height
    new_fw = int(orig_fw * frame_size_scale)
    new_fh = int(orig_fh * frame_size_scale)

    cx_f = (half_width + margin + wCam - margin) // 2 + frame_offset_x
    cy_f = (quarter_height + hCam - quarter_height) // 2 + frame_offset_y

    frame_left = cx_f - new_fw // 2
    frame_right = cx_f + new_fw // 2
    frame_top = cy_f - new_fh // 2
    frame_bottom = cy_f + new_fh // 2
    frame_box = (frame_left, frame_top, frame_right, frame_bottom)

    # 重新初始化 detector（如果需要）
    if confidence_changed:
        detector = init_detector()
        confidence_changed = False

    frame_count += 1
    should_detect = frame_count % skip_frames == 0

    # 检测窗口可见性
    try:
        window_visible = cv2.getWindowProperty("Image", cv2.WND_PROP_VISIBLE) >= 1 if window_created else True
    except Exception:
        window_visible = False

    # 手部检测
    if should_detect:
        if window_visible:
            img = detector.findHands(img)
        lmList = detector.findPosition(img, draw=False)
        has_hand = len(lmList) != 0
        if has_hand:
            last_lmList = lmList.copy()
    else:
        lmList = last_lmList if has_hand else []

    # 统一手势处理
    clocX, clocY, should_click, scroll_delta = process_gestures(
        lmList, detector, frame_box, (wScr, hScr),
        direction_offset, (plocX, plocY), smoothening
    )

    # 执行鼠标动作
    if len(lmList) != 0:
        fingers = detector.fingersUp()

        # 移动
        if fingers[1] and not fingers[2]:
            if abs(clocX - plocX) > 1 or abs(clocY - plocY) > 1:
                autopy.mouse.move(wScr - clocX, clocY)
            plocX, plocY = clocX, clocY

        # 点击
        if should_click:
            if window_visible:
                length, img, pinfo = detector.findDistance(8, 12, img, draw=True)
                if length < 40:
                    cv2.circle(img, (pinfo[4], pinfo[5]), 15, (0, 255, 0), cv2.FILLED)
                    autopy.mouse.click()
            else:
                autopy.mouse.click()

        # 滚轮
        if scroll_delta != 0:
            pyautogui.scroll(scroll_delta)

    # ---- 窗口最小化：跳过 UI 渲染 ----
    if not window_visible:
        key = cv2.waitKey(5)
        if key == 27:
            break
        continue

    # ---- 正常模式 UI 渲染 ----
    cv2.rectangle(img, (frame_left, frame_top), (frame_right, frame_bottom), (0, 255, 0), 2)

    # 移动模式圆圈
    if len(lmList) != 0 and fingers[1] and not fingers[2]:
        x1, y1 = lmList[8][1:]
        cv2.circle(img, (x1, y1), 15, (255, 0, 255), cv2.FILLED)

    # 方向控制模式（全屏覆盖）
    if show_direction_control:
        img = draw_direction_control(img)
        cv2.imshow("Image", img)
        window_created = True
        key = cv2.waitKey(1)
        if key == ord('e') or key == ord('E'):
            show_direction_control = False
            print("退出方向调整模式")
        elif key == 27:
            break
        continue

    # 帧率和 UI
    cTime = time.time()
    fps = 1 / (cTime - pTime) if cTime != pTime else 0
    pTime = cTime

    cv2.putText(img, f'fps:{int(fps)}', [15, 25],
                cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)
    img = draw_chinese_text(img, 'esc关闭', (15, hCam - 15), 20, (0, 255, 0))
    cv2.putText(img, 'Made by fanfan', (wCam - 150, 25),
                cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)
    img = draw_chinese_text(img, '按 Q 键调整方向', (15, hCam - 45), 16, (255, 255, 0))
    img = draw_chinese_text(img, '按 + 放大框 按 - 缩小框', (15, hCam - 70), 14, (255, 255, 0))
    img = draw_chinese_text(img, '方向键或WASD移动框', (15, hCam - 90), 12, (255, 255, 0))
    img = draw_chinese_text(img, f'置信度: {confidence_threshold:.2f}  Z降低 X提高', (15, hCam - 110), 11, (255, 255, 0))

    # 教程按钮
    cv2.rectangle(img, (button_x, button_y), (button_x + button_w, button_y + button_h), (100, 100, 255), -1)
    cv2.rectangle(img, (button_x, button_y), (button_x + button_w, button_y + button_h), (255, 255, 255), 2)
    img = draw_chinese_text(img, '教程', (button_x + 15, button_y + 20), 16, (255, 255, 255))

    if show_tutorial:
        img = draw_tutorial(img)

    cv2.imshow("Image", img)
    window_created = True

    # 键盘控制
    key = cv2.waitKey(1)
    if key == 27:
        break
    elif key == ord('q') or key == ord('Q'):
        show_direction_control = True
        print("进入方向调整模式")
    elif key == ord('+') or key == ord('='):
        frame_size_scale = min(frame_size_scale + 0.1, 2.0)
        save_config()
        print(f"框大小放大为: {frame_size_scale:.1f}")
    elif key == ord('-') or key == ord('_'):
        frame_size_scale = max(frame_size_scale - 0.1, 0.3)
        save_config()
        print(f"框大小缩小为: {frame_size_scale:.1f}")
    elif key == 81 or key == 2424832 or key == ord('a') or key == ord('A'):
        frame_offset_x -= 5
        save_config()
        print(f"框左移，X偏移: {frame_offset_x}")
    elif key == 83 or key == 2555904 or key == ord('d') or key == ord('D'):
        frame_offset_x += 5
        save_config()
        print(f"框右移，X偏移: {frame_offset_x}")
    elif key == 82 or key == 2490368 or key == ord('w') or key == ord('W'):
        frame_offset_y -= 5
        save_config()
        print(f"框上移，Y偏移: {frame_offset_y}")
    elif key == 84 or key == 2621440 or key == ord('s') or key == ord('S'):
        frame_offset_y += 5
        save_config()
        print(f"框下移，Y偏移: {frame_offset_y}")
    elif key == ord('z') or key == ord('Z'):
        confidence_threshold = max(confidence_threshold - 0.05, 0.1)
        confidence_changed = True
        save_config()
        print(f"置信度降低为: {confidence_threshold:.2f}")
    elif key == ord('x') or key == ord('X'):
        confidence_threshold = min(confidence_threshold + 0.05, 0.95)
        confidence_changed = True
        save_config()
        print(f"置信度提高为: {confidence_threshold:.2f}")
    elif key == ord('h') or key == ord('H'):
        show_tutorial = not show_tutorial
        print(f"教程显示: {'开启' if show_tutorial else '关闭'}")

save_config()
cap.release()
cv2.destroyAllWindows()

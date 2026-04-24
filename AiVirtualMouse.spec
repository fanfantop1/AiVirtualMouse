# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import mediapipe

# 获取 mediapipe 模块的路径
mediapipe_path = os.path.dirname(mediapipe.__file__)
# 直接包含整个 mediapipe 模块的所有文件
mediapipe_datas = [(mediapipe_path, 'mediapipe')]

a = Analysis(['AiVirtualMouse.py'],
             pathex=['C:\\Users\\fanfan\\Desktop\\CvApplication\\AiVirtualMouse'],
             binaries=[],
             datas=mediapipe_datas,
             hiddenimports=['mediapipe', 'cv2', 'autopy', 'numpy', 'pyautogui'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='AiVirtualMouse',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='mouse_icon.ico')

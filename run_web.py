# -*- coding: utf-8 -*-
"""
app.py(Streamlit 웹 UI)를 exe로 패키징하기 위한 런처.

PyInstaller로 이 파일을 빌드하면, exe를 더블클릭했을 때
1) 로컬 웹서버가 뜨고
2) 기본 브라우저가 자동으로 열리면서 app.py 화면이 나옵니다.

직접 실행할 때도 그냥 이렇게 쓰면 됩니다:
    python run_web.py
(streamlit run app.py 와 동일하게 동작함)
"""

import os
import sys

from streamlit.web import cli as stcli


def resource_path(relative_path: str) -> str:
    """PyInstaller로 묶였을 때(_MEIPASS 임시폴더)와 일반 실행일 때
    모두 올바른 경로를 찾기 위한 헬퍼."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        resource_path("app.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())

import base64
import io
from datetime import datetime

import streamlit as st
from PIL import Image, ImageOps

from camera_component import camera_capture

st.set_page_config(page_title="포토부스", page_icon="📸", layout="centered")

# --------------------------------------------------------------------------
# Frame definitions
# Each frame image has 4 photo "slots". Coordinates were measured directly
# from the provided frame images (pixel boxes: x0, y0, x1, y1), listed in the
# order photos should be taken / placed (top to bottom).
# --------------------------------------------------------------------------
FRAMES = {
    "frame3": {
        "label": "하트 & 클로버 (블루)",
        "path": "assets/frame3.jpg",
        "slots": [
            (373, 74, 674, 436),
            (38, 250, 339, 612),
            (373, 451, 674, 813),
            (38, 627, 339, 988),
        ],
    },
    "frame2": {
        "label": "필름 스트립 (화이트)",
        "path": "assets/frame2.jpg",
        "slots": [
            (167, 79, 565, 378),
            (167, 416, 565, 715),
            (167, 754, 565, 1052),
            (167, 1091, 565, 1389),
        ],
    },
    "frame1": {
        "label": "필름 스트립 (블랙)",
        "path": "assets/frame1.jpg",
        "slots": [
            (246, 43, 514, 227),
            (246, 238, 514, 422),
            (246, 434, 514, 629),
            (246, 641, 514, 818),
        ],
    },
}

if "step" not in st.session_state:
    st.session_state.step = "select"
if "frame_key" not in st.session_state:
    st.session_state.frame_key = None
if "result_image" not in st.session_state:
    st.session_state.result_image = None


def slot_aspect_ratio(frame_key: str) -> float:
    x0, y0, x1, y1 = FRAMES[frame_key]["slots"][0]
    return (x1 - x0) / (y1 - y0)


def compose_final_image(frame_key: str, photo_data_urls):
    frame_info = FRAMES[frame_key]
    frame_img = Image.open(frame_info["path"]).convert("RGB")
    result = frame_img.copy()

    for (x0, y0, x1, y1), data_url in zip(frame_info["slots"], photo_data_urls):
        header, encoded = data_url.split(",", 1)
        photo_bytes = base64.b64decode(encoded)
        photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")

        target_w, target_h = x1 - x0, y1 - y0
        fitted = ImageOps.fit(photo, (target_w, target_h), Image.LANCZOS)
        result.paste(fitted, (x0, y0))

    return result


def reset_to_start():
    st.session_state.step = "select"
    st.session_state.frame_key = None
    st.session_state.result_image = None


# --------------------------------------------------------------------------
# STEP 1: select a frame
# --------------------------------------------------------------------------
def render_select_step():
    st.title("📸 포토부스")
    st.write("먼저 마음에 드는 프레임을 선택해주세요.")

    cols = st.columns(3)
    for col, key in zip(cols, FRAMES.keys()):
        info = FRAMES[key]
        with col:
            st.image(info["path"], use_container_width=True)
            selected = st.session_state.frame_key == key
            btn_label = "✅ 선택됨" if selected else "이 프레임 선택"
            if st.button(btn_label, key=f"choose_{key}", use_container_width=True):
                st.session_state.frame_key = key
                st.rerun()
            st.caption(info["label"])

    st.divider()
    disabled = st.session_state.frame_key is None
    if st.button("🎬 촬영 시작하기", type="primary", use_container_width=True, disabled=disabled):
        st.session_state.step = "shoot"
        st.rerun()

    if disabled:
        st.info("프레임을 하나 선택하면 시작 버튼이 활성화됩니다.")


# --------------------------------------------------------------------------
# STEP 2: shoot 4 photos via the camera component
# --------------------------------------------------------------------------
def render_shoot_step():
    frame_key = st.session_state.frame_key
    st.title("📷 촬영하기")
    st.write("카메라 화면 가운데 창에 맞춰 포즈를 잡고 '촬영 시작'을 눌러주세요. "
             "3-2-1 카운트다운 후 자동으로 4번 촬영됩니다.")

    aspect = slot_aspect_ratio(frame_key)
    result = camera_capture(aspect_ratio=aspect, shots=4, height=680, key=f"cam_{frame_key}")

    if result and result.get("photos") and len(result["photos"]) == 4:
        final_img = compose_final_image(frame_key, result["photos"])
        st.session_state.result_image = final_img
        st.session_state.step = "result"
        st.rerun()

    st.divider()
    if st.button("⬅️ 프레임 다시 선택하기"):
        reset_to_start()
        st.rerun()


# --------------------------------------------------------------------------
# STEP 3: show result, allow download or retake
# --------------------------------------------------------------------------
def render_result_step():
    st.title("🎉 완성!")
    st.write("촬영한 사진이 프레임에 맞춰 완성되었습니다.")

    final_img = st.session_state.result_image
    st.image(final_img, use_container_width=True)

    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    buf.seek(0)
    filename = f"photobooth_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "💾 저장하기 (PNG)",
            data=buf,
            file_name=filename,
            mime="image/png",
            type="primary",
            use_container_width=True,
        )
    with col2:
        if st.button("🔄 다시 하기", use_container_width=True):
            reset_to_start()
            st.rerun()


# --------------------------------------------------------------------------
# router
# --------------------------------------------------------------------------
if st.session_state.step == "select":
    render_select_step()
elif st.session_state.step == "shoot":
    render_shoot_step()
elif st.session_state.step == "result":
    render_result_step()

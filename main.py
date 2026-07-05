import base64
import io
import os
import tempfile
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps

st.set_page_config(page_title="포토부스", page_icon="📸", layout="centered")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# Camera widget: a Streamlit custom component written in plain HTML/JS.
# It is embedded here as a string (instead of a separate frontend folder)
# so the whole app is a single file with no risk of missing sub-files when
# deploying to Streamlit Community Cloud.
# --------------------------------------------------------------------------
_CAMERA_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<style>
  html, body {
    margin: 0; padding: 0;
    background: #000;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif;
    overflow: hidden;
  }
  #stage {
    position: relative;
    width: 100%;
    height: var(--stage-height, 700px);
    background: #111;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  video {
    position: absolute;
    top: 50%; left: 50%;
    min-width: 100%; min-height: 100%;
    width: auto; height: auto;
    transform: translate(-50%, -50%) scaleX(-1); /* mirror like a mirror */
    object-fit: cover;
  }
  /* dark overlay with a transparent "window" cut out in the middle,
     so the camera is only clearly visible through the frame's photo slot */
  #frameWindow {
    position: relative;
    z-index: 5;
    box-shadow: 0 0 0 9999px rgba(0,0,0,0.62);
    border: 3px solid rgba(255,255,255,0.9);
    border-radius: 10px;
  }
  #countdown {
    position: absolute;
    z-index: 20;
    top: 0; left: 0; right: 0; bottom: 0;
    display: none;
    align-items: center;
    justify-content: center;
    font-size: 140px;
    font-weight: 800;
    color: #fff;
    text-shadow: 0 4px 24px rgba(0,0,0,0.6);
  }
  #flash {
    position: absolute;
    z-index: 30;
    top:0; left:0; right:0; bottom:0;
    background: #fff;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s ease-out;
  }
  #topbar {
    position: absolute;
    top: 14px; left: 0; right: 0;
    z-index: 15;
    display: flex;
    justify-content: center;
  }
  #counter {
    background: rgba(0,0,0,0.55);
    color: #fff;
    padding: 6px 18px;
    border-radius: 999px;
    font-size: 15px;
    letter-spacing: 0.5px;
  }
  #bottombar {
    position: absolute;
    bottom: 22px; left: 0; right: 0;
    z-index: 15;
    display: flex;
    justify-content: center;
    gap: 12px;
  }
  button.ctrl {
    background: #fff;
    color: #111;
    border: none;
    border-radius: 999px;
    padding: 14px 34px;
    font-size: 17px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(0,0,0,0.35);
  }
  button.ctrl:active { transform: scale(0.97); }
  button.secondary {
    background: rgba(255,255,255,0.15);
    color: #fff;
    border: 1px solid rgba(255,255,255,0.6);
  }
  #status {
    position: absolute;
    z-index: 15;
    bottom: 90px;
    left: 0; right: 0;
    text-align: center;
    color: #fff;
    font-size: 14px;
    opacity: 0.85;
  }
</style>
</head>
<body>

<div id="stage">
  <video id="video" autoplay playsinline muted></video>
  <div id="frameWindow"></div>
  <div id="countdown"></div>
  <div id="flash"></div>
  <div id="topbar"><div id="counter">촬영 대기 중</div></div>
  <div id="status"></div>
  <div id="bottombar">
    <button class="ctrl secondary" id="fullscreenBtn" type="button">전체화면</button>
    <button class="ctrl" id="startBtn" type="button">촬영 시작</button>
  </div>
</div>

<canvas id="canvas" style="display:none;"></canvas>

<script>
  const SET_COMPONENT_VALUE = "streamlit:setComponentValue";
  const RENDER = "streamlit:render";
  const COMPONENT_READY = "streamlit:componentReady";
  const SET_FRAME_HEIGHT = "streamlit:setFrameHeight";

  function _sendMessage(type, data) {
    const outboundData = Object.assign({ isStreamlitMessage: true, type: type }, data);
    window.parent.postMessage(outboundData, "*");
  }

  function setFrameHeight(height) {
    _sendMessage(SET_FRAME_HEIGHT, { height: height });
  }

  function notifyHost(value) {
    _sendMessage(SET_COMPONENT_VALUE, { value: value, dataType: "json" });
  }

  let aspectRatio = 1.0;
  let totalShots = 4;
  let stageHeight = 700;
  let videoStream = null;
  let capturedPhotos = [];
  let sequenceRunning = false;
  let initialized = false;

  function onRender(args) {
    if (!args) return;
    aspectRatio = args.aspectRatio || 1.0;
    totalShots = args.shots || 4;
    stageHeight = args.height || 700;
    document.getElementById("stage").style.setProperty("--stage-height", stageHeight + "px");
    layoutWindow();
    if (!initialized) {
      initialized = true;
      initCamera();
    }
  }

  window.addEventListener("message", (event) => {
    if (event.data.type === RENDER) {
      onRender(event.data.args);
    }
  });

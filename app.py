# -*- coding: utf-8 -*-
"""
코레일 이용 환경 편익 계산기 - 웹 UI (Streamlit)

실행:
    streamlit run app.py

팀원과 같은 네트워크에서 공유하려면:
    streamlit run app.py --server.address 0.0.0.0 --server.port 8501
그다음 팀원은 http://<이 컴퓨터의 사내망 IP>:8501 로 접속.
"""

import streamlit as st

from calculator import run, RAIL_GRADES

MODE_LABEL = {"ktx": "KTX", "mugunghwa": "무궁화호", "saemaul": "새마을호"}
MODE_COLOR = {"ktx": "#0B6E4F", "mugunghwa": "#3A8DFF", "saemaul": "#2FB380"}

LEG_LABEL = {
    "car": "🚗 전체 구간 (자차)",
    "car(access→terminal)": "🚗 출발지 → 터미널",
    "express_bus": "🚌 터미널 → 터미널 (고속버스)",
    "car(terminal→dest)": "🚗 터미널 → 도착지",
    "car(access→station)": "🚗 출발지 → 역",
    "car(station→dest)": "🚗 역 → 도착지",
    "ktx": "🚄 역 → 역 (KTX)",
    "mugunghwa": "🚆 역 → 역 (무궁화호)",
    "saemaul": "🚆 역 → 역 (새마을호)",
}


def _render_leg_detail(legs):
    """구간별 전체 경로(접근 자차 구간 포함)를 펼쳐서 보여준다."""
    for leg in legs:
        label = LEG_LABEL.get(leg.mode, leg.mode)
        st.markdown(f"**{label}** · {leg.km:.1f} km · {leg.co2_kg:.3f} kg CO2eq")
        if leg.route:
            st.markdown(
                f'<div class="route-line">{" → ".join(leg.route)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("경로 정보 없음")

st.set_page_config(
    page_title="코레일 환경편익 계산기",
    page_icon="🚆",
    layout="wide",
)

# ---------------------------------------------------------------------------
# 스타일
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans KR', sans-serif; }

    .block-container { padding-top: 2.2rem; max-width: 1100px; }

    .hero {
        background: linear-gradient(135deg, #0B6E4F 0%, #0E4B3A 100%);
        color: #F4FBF7;
        border-radius: 18px;
        padding: 28px 32px;
        margin-bottom: 24px;
    }
    .hero h1 { margin: 0 0 6px 0; font-size: 1.7rem; font-weight: 700; }
    .hero p { margin: 0; opacity: 0.85; font-size: 0.95rem; }

    .result-card {
        border: 1px solid #E4E9E7;
        border-radius: 14px;
        padding: 18px 20px;
        background: #FFFFFF;
    }
    .result-card h4 { margin-top: 0; margin-bottom: 4px; }
    .result-metric { font-size: 1.6rem; font-weight: 700; margin: 2px 0; }
    .result-sub { color: #6B7A76; font-size: 0.85rem; }

    .route-line {
        font-size: 0.82rem;
        color: #46564F;
        background: #F1F6F3;
        border-radius: 8px;
        padding: 6px 10px;
        margin-top: 6px;
        word-break: break-all;
    }
    .benefit-pill {
        display: inline-block;
        background: #EAF7EF;
        color: #0B6E4F;
        border-radius: 999px;
        padding: 4px 14px;
        font-weight: 600;
        font-size: 0.9rem;
        margin-right: 8px;
    }
    .warn-note {
        color: #A9660A;
        font-size: 0.82rem;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>🚆 코레일 이용 환경 편익 계산기</h1>
      <p>출발지·도착지·탑승 인원을 입력하면 자차/고속버스/철도의 탄소·미세먼지
      배출량을 실제 도로거리·역간거리 기준으로 비교합니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 입력
# ---------------------------------------------------------------------------
with st.form("input_form"):
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        passengers = st.number_input("탑승 인원수", min_value=1, value=1, step=1)
    with c2:
        origin = st.text_input("출발지", placeholder="예: 서울시 강남구 테헤란로 152")
    with c3:
        dest = st.text_input("도착지", placeholder="예: 부산 해운대구 달맞이길 30")
    submitted = st.form_submit_button("환경 편익 계산하기", use_container_width=True)

if submitted:
    if not origin.strip() or not dest.strip():
        st.error("출발지와 도착지를 모두 입력해주세요.")
        st.stop()

    with st.spinner("주소 확인 및 경로 계산 중..."):
        try:
            result = run(origin, dest, passengers=int(passengers))
        except Exception as e:
            st.error(f"계산 중 문제가 발생했습니다: {e}")
            st.info(
                "흔한 원인: 주소가 너무 모호함 / API 키 미설정·오류 / "
                "카카오·구글 API 활성화 상태 확인 필요"
            )
            st.stop()

    st.success(f"탑승 인원 {passengers}명 기준으로 계산했습니다.")

    # ------------------------------------------------------------------
    # 자차 / 고속버스
    # ------------------------------------------------------------------
    col_car, col_bus = st.columns(2)

    with col_car:
        st.markdown(
            f"""
            <div class="result-card">
              <h4>🚗 자차</h4>
              <div class="result-metric">{result.car.total_co2_kg:.2f} kg CO2eq</div>
              <div class="result-sub">미세먼지 {result.car.total_pm25_kg*1000:.2f} g · {result.car.total_km:.1f} km</div>
              <div class="route-line">{" → ".join(result.car.legs[0].route) if result.car.legs[0].route else "경로 정보 없음"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_bus:
        bus_leg = next(l for l in result.bus.legs if l.mode == "express_bus")
        st.markdown(
            f"""
            <div class="result-card">
              <h4>🚌 고속버스</h4>
              <div class="result-metric">{result.bus.total_co2_kg:.2f} kg CO2eq</div>
              <div class="result-sub">미세먼지 {result.bus.total_pm25_kg*1000:.2f} g · {result.bus.total_km:.1f} km</div>
              <div class="route-line">{" → ".join(bus_leg.route) if bus_leg.route else "경로 정보 없음"}</div>
              <div class="result-sub" style="margin-top:6px;">{" / ".join(result.bus.notes)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("전체 경로 보기 (출발지→터미널 포함)"):
            _render_leg_detail(result.bus.legs)

    st.markdown("<br>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 철도 (3등급)
    # ------------------------------------------------------------------
    st.markdown("#### 🚄 철도 (등급별)")
    rail_cols = st.columns(3)
    for col, mode in zip(rail_cols, RAIL_GRADES):
        r = result.rail[mode]
        rail_leg = next(l for l in r.legs if l.mode == mode)
        route_preview = rail_leg.route
        route_str = " → ".join(route_preview) if len(route_preview) <= 6 else (
            " → ".join(route_preview[:3]) + f" → ... ({len(route_preview)}개 역) ... → " + " → ".join(route_preview[-2:])
        )
        warn = "".join(f'<div class="warn-note">{n}</div>' for n in r.notes if n.startswith("⚠"))
        with col:
            st.markdown(
                f"""
                <div class="result-card" style="border-top:4px solid {MODE_COLOR[mode]};">
                  <h4>{MODE_LABEL[mode]}</h4>
                  <div class="result-metric" style="color:{MODE_COLOR[mode]};">{r.total_co2_kg:.2f} kg CO2eq</div>
                  <div class="result-sub">미세먼지 {r.total_pm25_kg*1000:.2f} g · {r.total_km:.1f} km</div>
                  <div class="route-line">{route_str}</div>
                  {warn}
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("전체 경로 보기 (역 접근구간 포함)"):
                _render_leg_detail(r.legs)

    st.caption("경유 경로는 선로 기준 실제 경로이며, 열차가 그 역들에 정차한다는 뜻은 아닙니다.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 편익 요약
    # ------------------------------------------------------------------
    st.markdown("#### 🌱 철도 이용 시 환경 편익")
    b_car = result.benefit_vs_car()
    b_bus = result.benefit_vs_bus()

    for mode in RAIL_GRADES:
        bc, bb = b_car[mode], b_bus[mode]
        st.markdown(
            f"""
            <div style="margin-bottom:10px;">
              <b>{MODE_LABEL[mode]}</b><br>
              <span class="benefit-pill">자차 대비 CO2 {bc['co2_kg_saved']:.2f} kg 절감</span>
              <span class="benefit-pill">자차 대비 PM2.5 {bc['pm25_kg_saved']*1000:.2f} g 절감</span>
              <span class="benefit-pill">버스 대비 CO2 {bb['co2_kg_saved']:.2f} kg 절감</span>
              <span class="benefit-pill">버스 대비 PM2.5 {bb['pm25_kg_saved']*1000:.2f} g 절감</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if bb["co2_kg_saved"] < 0:
            st.caption(
                f"※ {MODE_LABEL[mode]}는 배출계수 자체가 고속버스보다 높아 "
                "버스 대비 편익이 음수(더 많이 배출)로 나올 수 있습니다."
            )

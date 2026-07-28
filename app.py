# -*- coding: utf-8 -*-
"""
코레일 이용 환경 편익 계산기 - 웹 UI (Streamlit)

실행:
    streamlit run app.py

팀원과 같은 네트워크에서 공유하려면:
    streamlit run app.py --server.address 0.0.0.0 --server.port 8501
그다음 팀원은 http://<이 컴퓨터의 사내망 IP>:8501 로 접속.

🔧 수정사항:
- 캐시 TTL 1800초 → 300초로 단축
- 편명 표시 로직 강화
- 경로 라벨 개선
"""

import streamlit as st
from datetime import datetime, date, timedelta
import pytz

from calculator import run, RAIL_GRADES
from transit_distance import format_time

# KST 타임존 설정
KST = pytz.timezone('Asia/Seoul')

# Session state 초기화 (사용자 입력값 유지)
if 'travel_date' not in st.session_state:
    st.session_state.travel_date = date.today()
if 'travel_time' not in st.session_state:
    st.session_state.travel_time = datetime.now(KST).time()
if 'origin' not in st.session_state:
    st.session_state.origin = ""
if 'dest' not in st.session_state:
    st.session_state.dest = ""
if 'passengers' not in st.session_state:
    st.session_state.passengers = 1

# 🔧 CPU 사용량 최소화: 계산 결과 캐싱 (TTL: 5분, 변경감지: origin+dest+passengers)
# 기존: ttl=1800 (30분) → 문제: 오래된 빈 결과를 계속 반환
# 개선: ttl=300 (5분) → 신선한 데이터 유지
@st.cache_data(ttl=300, show_spinner=False)  
def cached_run(origin, dest, passengers, travel_time_str):
    """API 호출 결과를 5분 동안 캐싱하여 CPU 절감"""
    return run(origin, dest, passengers=passengers, travel_time_str=travel_time_str)

MODE_LABEL = {
    "ktx": "KTX", 
    "mugunghwa": "무궁화호", 
    "saemaul": "새마을호",
    "itx-saemaul": "ITX-새마을"
}
MODE_COLOR = {
    "ktx": "#0B6E4F", 
    "mugunghwa": "#3A8DFF", 
    "saemaul": "#2FB380",
    "itx-saemaul": "#FF8C42"  # 주황색으로 구분
}

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
    "itx-saemaul": "🚆 역 → 역 (ITX-새마을)",
}


def _render_leg_detail(legs):
    """구간별 전체 경로(접근 자차 구간 포함)를 펼쳐서 보여준다."""
    for leg in legs:
        label = LEG_LABEL.get(leg.mode, leg.mode)
        time_str = f" · {format_time(leg.duration_seconds)}" if leg.duration_seconds > 0 else ""
        st.markdown(f"**{label}** · {leg.km:.1f} km · {leg.co2_kg:.3f} kg CO2eq{time_str}")
        
        # 열차 정보 표시
        if leg.train_info and leg.train_info.get("trainno"):
            train_no = leg.train_info.get("trainno", "")
            dep_time = leg.train_info.get("deptime", "")
            arr_time = leg.train_info.get("arrtime", "")
            fare = leg.train_info.get("fare", 0)
            st.caption(f"🚆 {train_no} · {dep_time}→{arr_time} · 요금: {fare:,}원")
        
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
    .result-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 16px;
        border-radius: 12px;
        border-left: 4px solid #0B6E4F;
        margin-bottom: 12px;
    }
    .result-metric {
        font-size: 24px;
        font-weight: bold;
        color: #0B6E4F;
        margin: 8px 0;
    }
    .result-sub {
        font-size: 14px;
        color: #555;
    }
    .route-line {
        background: #fafafa;
        padding: 8px;
        border-radius: 6px;
        font-size: 12px;
        color: #666;
        margin-top: 6px;
        word-break: break-word;
    }
    .warn-note {
        background: #fff3cd;
        padding: 6px;
        border-radius: 4px;
        font-size: 12px;
        color: #856404;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 헤더
# ---------------------------------------------------------------------------
st.markdown("# 🚆 코레일 환경편익 계산기")
st.markdown("**출발지 → 도착지 경로에서 자차/버스/철도 3가지 교통수단의 탄소·미세먼지 배출량을 비교합니다.**")
st.markdown("**철도 이용 시 자차/버스 대비 환경 편익을 한눈에 파악하세요.**")
st.markdown("")

# ---------------------------------------------------------------------------
# 입력 양식
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

with col1:
    origin = st.text_input(
        "📍 출발지 (주소·지명)",
        value=st.session_state.origin,
        key="origin_input",
        placeholder="예: 서울역, 강남역"
    )
    st.session_state.origin = origin

with col2:
    dest = st.text_input(
        "📍 도착지 (주소·지명)",
        value=st.session_state.dest,
        key="dest_input",
        placeholder="예: 부산역, 목포"
    )
    st.session_state.dest = dest

with col3:
    passengers = st.number_input(
        "👥 탑승인원",
        min_value=1,
        max_value=20,
        value=st.session_state.passengers,
        key="passengers_input"
    )
    st.session_state.passengers = int(passengers)

with col4:
    search_btn = st.button("🔍 검색", use_container_width=True)

# 여행 시간 선택 (선택사항)
col_time1, col_time2 = st.columns([1, 1])

with col_time1:
    travel_date = st.date_input(
        "📅 여행 날짜 (선택사항)",
        value=st.session_state.travel_date,
        key="travel_date_input"
    )
    st.session_state.travel_date = travel_date

with col_time2:
    travel_time = st.time_input(
        "🕐 출발 시각 (선택사항)",
        value=st.session_state.travel_time,
        key="travel_time_input"
    )
    st.session_state.travel_time = travel_time

# ---------------------------------------------------------------------------
# 결과
# ---------------------------------------------------------------------------
if search_btn or (origin and dest):
    if not origin or not dest:
        st.warning("⚠️ 출발지와 도착지를 입력하세요.")
    else:
        status_placeholder = st.empty()
        status_placeholder.info("📊 계산 중... (5-10초 소요)")
        
        try:
            travel_time_str = travel_time.strftime("%H:%M")
            result = cached_run(origin, dest, int(passengers), travel_time_str)
            status_placeholder.empty()
            
            # 자차
            st.markdown("#### 🚗 자동차")
            car_leg = result.car.legs[0]
            time_str = f" · {format_time(result.car.total_duration_seconds)}" if result.car.total_duration_seconds > 0 else ""
            st.markdown(
                f"""
                <div class="result-card">
                  <h4>🚗 자동차</h4>
                  <div class="result-metric">{result.car.total_co2_kg:.2f} kg CO2eq</div>
                  <div class="result-sub">미세먼지 {result.car.total_pm25_kg*1000:.2f} g · {result.car.total_km:.1f} km{time_str}</div>
                  <div class="route-line">{" → ".join(car_leg.route) if car_leg.route else "경로 정보 없음"}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # 고속버스
            st.markdown("#### 🚌 고속버스")
            bus_leg = next(l for l in result.bus.legs if l.mode == "express_bus")
            time_str = f" · {format_time(result.bus.total_duration_seconds)}" if result.bus.total_duration_seconds > 0 else ""
            st.markdown(
                f"""
                <div class="result-card">
                  <h4>🚌 고속버스</h4>
                  <div class="result-metric">{result.bus.total_co2_kg:.2f} kg CO2eq</div>
                  <div class="result-sub">미세먼지 {result.bus.total_pm25_kg*1000:.2f} g · {result.bus.total_km:.1f} km{time_str}</div>
                  <div class="route-line">{" → ".join(bus_leg.route) if bus_leg.route else "경로 정보 없음"}</div>
                  <div class="result-sub" style="margin-top:6px;">{" / ".join(result.bus.notes)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("전체 경로 보기 (출발지→터미널 포함)"):
                _render_leg_detail(result.bus.legs)

            st.markdown("<br>", unsafe_allow_html=True)

            # 철도 (4등급)
            st.markdown("#### 🚄 철도 (등급별)")
            rail_cols = st.columns(4)  # 4개 등급이므로 4개 열
            for col, mode in zip(rail_cols, RAIL_GRADES):
                r = result.rail[mode]
                rail_leg = next(l for l in r.legs if l.mode == mode)
                route_preview = rail_leg.route
                route_str = " → ".join(route_preview) if len(route_preview) <= 6 else (
                    " → ".join(route_preview[:3]) + f" → ... ({len(route_preview)}개 역) ... → " + " → ".join(route_preview[-2:])
                )
                
                # 🔧 경로 라벨: 정차역 vs 선로 경로
                # 정차역은 실제 역명들이고, 선로 경로는 Dijkstra 결과
                is_actual_stops = len(route_preview) > 0 and route_preview != list(rail_leg.route)
                route_label = "정차역" if len(route_preview) > 0 else "선로 경로"
                route_str_with_label = f"<small style='color:#666;'>📍 {route_label}:</small> {route_str}"
                
                warn = "".join(f'<div class="warn-note">{n}</div>' for n in r.notes if n.startswith("⚠"))
                
                with col:
                    time_str = f" · {format_time(r.total_duration_seconds)}" if r.total_duration_seconds > 0 else ""
                    
                    # 🔧 열차 정보 (편명, 출발/도착 시간) - 강화된 로직
                    train_info_str = ""
                    if rail_leg.train_info and isinstance(rail_leg.train_info, dict) and rail_leg.train_info:
                        train_info = rail_leg.train_info
                        train_no = train_info.get("trainno") or train_info.get("train_no") or ""
                        dep_time = train_info.get("deptime") or train_info.get("dep_time") or ""
                        arr_time = train_info.get("arrtime") or train_info.get("arr_time") or ""
                        
                        # 모두 있을 때만 표시
                        if train_no and dep_time and arr_time:
                            train_info_str = f'<div class="result-sub" style="color:#FF6B6B; font-weight: bold;">🚆 편명 {train_no} · {dep_time}→{arr_time}</div>'
                    
                    st.markdown(
                        f"""
                        <div class="result-card">
                          <h4>{MODE_LABEL.get(mode, mode)}</h4>
                          <div class="result-metric">{r.total_co2_kg:.2f} kg CO2eq</div>
                          <div class="result-sub">미세먼지 {r.total_pm25_kg*1000:.2f} g · {r.total_km:.1f} km{time_str}</div>
                          {train_info_str}
                          <div class="route-line">{route_str_with_label}</div>
                          {warn}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    
                    with st.expander("전체 경로 보기"):
                        _render_leg_detail(r.legs)

            st.markdown("<br>", unsafe_allow_html=True)

            # 환경 편익 비교
            st.markdown("#### 🌍 환경 편익 분석")
            st.markdown("**철도 vs 자동차**")
            
            benefits_vs_car = result.benefit_vs_car()
            benefits_car_cols = st.columns(4)
            for col, mode in zip(benefits_car_cols, RAIL_GRADES):
                with col:
                    b = benefits_vs_car[mode]
                    co2_saved = b["co2_kg_saved"]
                    pm25_saved = b["pm25_kg_saved"]
                    st.metric(
                        f"{MODE_LABEL.get(mode, mode)} 절감량",
                        f"{co2_saved:.2f} kg CO2",
                        delta=f"{pm25_saved*1000:.1f}g PM2.5",
                    )

            st.markdown("**철도 vs 고속버스**")
            benefits_vs_bus = result.benefit_vs_bus()
            benefits_bus_cols = st.columns(4)
            for col, mode in zip(benefits_bus_cols, RAIL_GRADES):
                with col:
                    b = benefits_vs_bus[mode]
                    co2_saved = b["co2_kg_saved"]
                    pm25_saved = b["pm25_kg_saved"]
                    st.metric(
                        f"{MODE_LABEL.get(mode, mode)} 절감량",
                        f"{co2_saved:.2f} kg CO2",
                        delta=f"{pm25_saved*1000:.1f}g PM2.5",
                    )

        except Exception as e:
            status_placeholder.empty()
            st.error(f"❌ 계산 중 오류가 발생했습니다: {str(e)}")
            with st.expander("기술 상세 정보"):
                st.write(str(e))

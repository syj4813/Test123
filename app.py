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
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

# CPU 사용량 최소화: 계산 결과 캐싱 (TTL: 30분, 변경감지: origin+dest+passengers)
@st.cache_data(ttl=1800, show_spinner=False)  
def cached_run(origin, dest, passengers, travel_time_str):
    """API 호출 결과를 30분 동안 캐싱하여 CPU 절감"""
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
        passengers = st.number_input(
            "탑승 인원수", 
            min_value=1, 
            value=st.session_state.passengers, 
            step=1,
            key="passengers_input"
        )
    with c2:
        origin = st.text_input(
            "출발지", 
            placeholder="예: 서울시 강남구 테헤란로 152",
            value=st.session_state.origin,
            key="origin_input"
        )
    with c3:
        dest = st.text_input(
            "도착지", 
            placeholder="예: 부산 해운대구 달맞이길 30",
            value=st.session_state.dest,
            key="dest_input"
        )
    
    # 날짜/시간 선택 (KST 기본값)
    col_date, col_time = st.columns(2)
    with col_date:
        travel_date = st.date_input(
            "여행 날짜", 
            value=st.session_state.travel_date,
            key="date_input"
        )
    with col_time:
        travel_time = st.time_input(
            "출발시간 (참고용)", 
            value=st.session_state.travel_time,
            key="time_input"
        )
    
    submitted = st.form_submit_button("환경 편익 계산하기", use_container_width=True)

if submitted:
    if not origin.strip() or not dest.strip():
        st.error("출발지와 도착지를 모두 입력해주세요.")
        st.stop()

    # 입력값 저장 (다음 검색 시 유지)
    st.session_state.origin = origin
    st.session_state.dest = dest
    st.session_state.passengers = passengers
    st.session_state.travel_date = travel_date
    st.session_state.travel_time = travel_time

    try:
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        # 각 단계별 진행 상황 표시
        steps = [
            "🗺️ 주소 확인 중...",
            "🚗 자차 경로 계산 중...",
            "🚌 버스 경로 및 소요시간 조회 중...",
            "🚆 철도 경로 및 소요시간 조회 중 (TAGO API - 시간 소요)...",
        ]
        
        for i, step in enumerate(steps):
            status_placeholder.info(step)
        
        # 각 등급별로 병렬 조회
        status_placeholder.info("🚆 열차 정보 조회 중... (5-10초 소요)")
        
        # 캐싱된 계산 호출 (CPU 절감)
        result = cached_run(origin, dest, int(passengers), travel_time.strftime("%H:%M"))
        
        progress_placeholder.success("✅ 계산 완료!")
        status_placeholder.empty()

        # 🔧 FIX: 결과를 session_state에 저장 (버튼 클릭 등으로 재실행되어도 유지)
        st.session_state.last_result = result
        
    except Exception as e:
        st.error(f"계산 중 문제가 발생했습니다: {e}")
        st.info(
            "흔한 원인: 주소가 너무 모호함 / API 키 미설정·오류 / "
            "카카오·구글 API 활성화 상태 확인 필요"
        )
        st.session_state.last_result = None
        st.stop()

# 🔧 FIX: 렌더링을 submitted가 아니라 "저장된 결과가 있는지"로 분기
# → 디버그 버튼처럼 폼 밖의 위젯을 눌러 재실행되어도 결과 화면이 유지됨
if st.session_state.get("last_result") is not None:
    result = st.session_state.last_result
    origin = st.session_state.origin
    dest = st.session_state.dest
    passengers = st.session_state.passengers
    travel_date = st.session_state.travel_date
    travel_time = st.session_state.travel_time

    st.success(f"탑승 인원 {passengers}명 기준으로 계산했습니다.")
    st.info(f"📅 {travel_date.strftime('%Y년 %m월 %d일')} 🕐 {travel_time.strftime('%H:%M')} 출발 기준")

    # ------------------------------------------------------------------
    # 자차 / 고속버스
    # ------------------------------------------------------------------
    col_car, col_bus = st.columns(2)

    with col_car:
        time_str = f" · {format_time(result.car.total_duration_seconds)}" if result.car.total_duration_seconds > 0 else ""
        st.markdown(
            f"""
            <div class="result-card">
              <h4>🚗 자차</h4>
              <div class="result-metric">{result.car.total_co2_kg:.2f} kg CO2eq</div>
              <div class="result-sub">미세먼지 {result.car.total_pm25_kg*1000:.2f} g · {result.car.total_km:.1f} km{time_str}</div>
              <div class="route-line">{" → ".join(result.car.legs[0].route) if result.car.legs[0].route else "경로 정보 없음"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_bus:
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

    # ------------------------------------------------------------------
    # 철도 (3등급)
    # ------------------------------------------------------------------
    st.markdown("#### 🚄 철도 (등급별)")
    rail_cols = st.columns(4)  # 4개 등급이므로 4개 열
    for col, mode in zip(rail_cols, RAIL_GRADES):
        r = result.rail[mode]
        rail_leg = next(l for l in r.legs if l.mode == mode)
        route_preview = rail_leg.route
        route_str = " → ".join(route_preview) if len(route_preview) <= 6 else (
            " → ".join(route_preview[:3]) + f" → ... ({len(route_preview)}개 역) ... → " + " → ".join(route_preview[-2:])
        )
        # 정차역 API(GetTrainStopList)가 존재하지 않아 항상 Dijkstra 선로 경로 사용
        route_label = "선로 경로(참고용, 실제 정차역과 다를 수 있음)"
        route_str_with_label = f"<small style='color:#666;'>📍 {route_label}:</small> {route_str}"
        warn = "".join(f'<div class="warn-note">{n}</div>' for n in r.notes if n.startswith("⚠"))
        with col:
            rail_leg = next(l for l in r.legs if l.mode == mode)
            time_str = f" · {format_time(r.total_duration_seconds)}" if r.total_duration_seconds > 0 else ""
            
            # 열차 정보 (편명, 출발/도착 시간)
            train_info_str = ""
            if rail_leg.train_info and isinstance(rail_leg.train_info, dict):
                train_info = rail_leg.train_info
                # 여러 필드명 시도
                train_no = train_info.get("trainno") or train_info.get("train_no") or ""
                dep_time = train_info.get("deptime") or train_info.get("dep_time") or ""
                arr_time = train_info.get("arrtime") or train_info.get("arr_time") or ""
                
                # 모두 있을 때만 표시
                if train_no and dep_time and arr_time:
                    train_info_str = f'<div class="result-sub" style="color:#FF6B6B; font-weight: bold;">🚆 편명 {train_no} · {dep_time}→{arr_time}</div>'
            
            st.markdown(
                f"""
                <div class="result-card" style="border-top:4px solid {MODE_COLOR[mode]};">
                  <h4>{MODE_LABEL[mode]}</h4>
                  <div class="result-metric" style="color:{MODE_COLOR[mode]};">{r.total_co2_kg:.2f} kg CO2eq</div>
                  <div class="result-sub">미세먼지 {r.total_pm25_kg*1000:.2f} g · {r.total_km:.1f} km{time_str}</div>
                  {train_info_str}
                  <div class="route-line">{route_str_with_label}</div>
                  {warn}
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("전체 경로 보기 (역 접근구간 포함)"):
                _render_leg_detail(r.legs)

    st.caption("📍 선로 경로: Dijkstra 기반 선로상 경유역 (실제 정차역 API는 TAGO에서 미제공되어 사용 불가)")

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

    # ------------------------------------------------------------------
    # 🔧 임시 디버그: TAGO API 원본 응답 확인용 (문제 해결되면 삭제할 것)
    # ------------------------------------------------------------------
    with st.expander("🔧 [디버그] TAGO API 원본 응답 확인"):
        st.caption("편명/정차역이 안 보일 때, 이 버튼으로 실제 API가 뭘 돌려주는지 확인합니다.")

        dbg_col1, dbg_col2 = st.columns(2)
        with dbg_col1:
            dbg_dep_name = st.text_input("출발역명", value="서울", key="dbg_dep_name")
        with dbg_col2:
            dbg_arr_name = st.text_input("도착역명", value="부산", key="dbg_arr_name")

        if st.button("① 역ID 조회 + KTX 원본 응답 조회"):
            import requests as _requests
            try:
                _key = st.secrets.get("TAGO_API_KEY")
            except Exception:
                _key = None
            if not _key:
                st.error("TAGO_API_KEY가 Secrets에 없습니다.")
            else:
                import train_api_threading as _tat

                # MAJOR_STATIONS에 있는지부터 확인
                st.write(f"MAJOR_STATIONS 목록: {list(_tat.MAJOR_STATIONS.keys())}")
                _dep_id = _tat._get_station_id(dbg_dep_name, _key)
                _arr_id = _tat._get_station_id(dbg_arr_name, _key)
                st.write(f"출발역ID: `{_dep_id}` (비어있으면 조회 실패)")
                st.write(f"도착역ID: `{_arr_id}` (비어있으면 조회 실패)")

                if not _dep_id or not _arr_id:
                    st.warning("역ID 조회부터 실패했습니다. 아래 '② 도시코드 역 목록 조회'로 원인을 확인하세요.")
                else:
                    _url = f"{_tat.TAGO_BASE_URL}/GetStrtpntAlocFndTrainInfo"
                    _params = {
                        "serviceKey": _key,
                        "pageNo": 1,
                        "numOfRows": 20,
                        "_type": "json",
                        "depPlaceId": _dep_id,
                        "arrPlaceId": _arr_id,
                        "depPlandTime": "null",
                        "trainGradeCode": "00",
                    }
                    _resp = _requests.get(_url, params=_params, timeout=10)
                    st.write(f"HTTP 상태코드: `{_resp.status_code}`")
                    st.write(f"실제 요청 URL: `{_resp.url}`")
                    st.code(_resp.text[:3000], language="json")

        st.markdown("---")
        if st.button("② 도시코드 역 목록 조회 (서울=11)"):
            import requests as _requests
            try:
                _key = st.secrets.get("TAGO_API_KEY")
            except Exception:
                _key = None
            if not _key:
                st.error("TAGO_API_KEY가 Secrets에 없습니다.")
            else:
                import train_api_threading as _tat
                _url = f"{_tat.TAGO_BASE_URL}/GetCtyAcctoTrainSttnList"
                _params = {
                    "serviceKey": _key,
                    "pageNo": 1,
                    "numOfRows": 1000,
                    "_type": "json",
                    "cityCode": "11",
                }
                _resp = _requests.get(_url, params=_params, timeout=10)
                st.write(f"HTTP 상태코드: `{_resp.status_code}`")
                st.write(f"실제 요청 URL: `{_resp.url}`")
                st.code(_resp.text[:3000], language="json")

        st.markdown("---")
        if st.button("④ 최종 확인: GetCtyAcctoTrainSttnList (확정된 정답 주소)"):
            import requests as _requests
            try:
                _key = st.secrets.get("TAGO_API_KEY")
            except Exception:
                _key = None
            if not _key:
                st.error("TAGO_API_KEY가 Secrets에 없습니다.")
            else:
                _url = "https://apis.data.go.kr/1613000/TrainInfo/GetCtyAcctoTrainSttnList"
                _r = _requests.get(
                    _url,
                    params={
                        "serviceKey": _key,
                        "pageNo": 1,
                        "numOfRows": 5,
                        "_type": "json",
                        "cityCode": "11",
                    },
                    timeout=10,
                )
                st.write(f"상태코드: `{_r.status_code}`")
                st.code(_r.text[:1000], language="json")

        st.markdown("---")
        st.caption("⚠️ 아래 정차역 조회는 참고용입니다. 공식 오퍼레이션 목록에 "
                   "GetTrainStopList가 없어서 항상 404가 예상됩니다 (정차역 기능은 비활성화됨).")
        train_no_debug = st.text_input("③ 편명 직접 입력해서 정차역 조회 시도 (예: 05201)", key="debug_trainno")
        if st.button("정차역 원본 응답 조회") and train_no_debug:
            import requests as _requests
            try:
                _key = st.secrets.get("TAGO_API_KEY")
            except Exception:
                _key = None
            if not _key:
                st.error("TAGO_API_KEY가 Secrets에 없습니다.")
            else:
                import train_api_threading as _tat
                _url = f"{_tat.TAGO_BASE_URL}/getTrainStopList"
                _params = {
                    "serviceKey": _key,
                    "pageNo": 1,
                    "numOfRows": 100,
                    "_type": "json",
                    "trainNo": train_no_debug,
                }
                _resp = _requests.get(_url, params=_params, timeout=10)
                st.write(f"HTTP 상태코드: `{_resp.status_code}`")
                st.write(f"실제 요청 URL: `{_resp.url}`")
                st.code(_resp.text[:3000], language="json")

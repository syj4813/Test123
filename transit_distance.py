# -*- coding: utf-8 -*-
"""
카카오맵 공개 경로(Public Transit) API로 대중교통 이동시간/경로 산출.

버스/철도의 실제 소요시간, 거리, 환승 정보 등을 가져온다.
이미 발급받은 카카오 REST API 키로 사용 가능 (카카오맵 제품만 활성화).

엔드포인트: GET https://dapi.kakao.com/v2/routing/publictraffic
응답: 전체 경로, 각 구간별 소요시간, 대중교통 상세 정보
"""

import os
import requests


PUBLICTRAFFIC_URL = "https://dapi.kakao.com/v2/routing/publictraffic"


class TransitError(Exception):
    pass


def _get_key(api_key):
    """API 키 우선순위: 인자 → 환경변수 → Streamlit Secrets."""
    try:
        import streamlit as st
        return api_key or os.environ.get("KAKAO_REST_API_KEY") or st.secrets.get("KAKAO_REST_API_KEY")
    except:
        return api_key or os.environ.get("KAKAO_REST_API_KEY")


def transit_route(origin, destination, api_key: str = None) -> dict:
    """origin, destination: (lat, lng) 튜플.
    
    반환: {
        "duration_seconds": 총 소요시간(초),
        "distance_m": 총 거리(미터),
        "fare": 요금(원),
        "transfers": 환승 횟수,
        "summary": 경로 요약 (예: "버스 → 지하철"),
        "legs": 각 구간별 상세 정보 리스트
    }
    
    TransitError 발생 가능: API 호출 실패, 경로 없음 등
    """
    key = _get_key(api_key)
    if not key:
        raise TransitError(
            "KAKAO_REST_API_KEY가 설정되지 않았습니다 "
            "(환경변수 또는 Streamlit Secrets 확인)."
        )

    lat_o, lng_o = origin
    lat_d, lng_d = destination

    headers = {"Authorization": f"KakaoAK {key}"}
    params = {
        "origin": f"{lng_o},{lat_o}",
        "destination": f"{lng_d},{lat_d}",
        "sort": "recommend",  # 추천 경로
    }

    try:
        resp = requests.get(PUBLICTRAFFIC_URL, headers=headers, params=params, timeout=15)
    except requests.exceptions.Timeout:
        raise TransitError("카카오 대중교통 API 요청 시간 초과")
    except Exception as e:
        raise TransitError(f"카카오 API 호출 오류: {e}")

    if resp.status_code != 200:
        raise TransitError(
            f"카카오 대중교통 API 오류 (status={resp.status_code}): {resp.text[:200]}"
        )

    try:
        data = resp.json()
    except:
        raise TransitError("카카오 API 응답 파싱 실패")

    routes = data.get("routes", [])
    if not routes:
        raise TransitError("대중교통 경로를 찾을 수 없습니다.")

    route = routes[0]  # 추천 경로 (첫 번째)
    summary = route.get("summary", {})
    
    # 소요시간: 초 단위
    duration_seconds = summary.get("duration", 0)
    
    # 거리: 미터 단위
    distance_m = summary.get("distance", 0)
    
    # 요금: 원
    fare = summary.get("fare", {}).get("regular", 0)
    
    # 환승 횟수
    transfers = len([l for l in route.get("legs", []) if l.get("mode") != "WALK"])
    
    # 경로 요약 (예: "버스 → 지하철 → 도보")
    legs = route.get("legs", [])
    leg_types = []
    for leg in legs:
        mode = leg.get("mode", "")
        if mode == "BUS":
            leg_types.append("버스")
        elif mode == "SUBWAY":
            leg_types.append("지하철")
        elif mode == "WALK":
            leg_types.append("도보")
        elif mode == "TRAIN":
            leg_types.append("기차")
    
    summary_str = " → ".join(leg_types) if leg_types else "알 수 없음"
    
    return {
        "duration_seconds": duration_seconds,
        "distance_m": distance_m,
        "duration_minutes": duration_seconds // 60,
        "fare": fare,
        "transfers": transfers - 1 if transfers > 0 else 0,  # 도보는 제외
        "summary": summary_str,
        "legs": legs,
    }


def format_time(seconds: int) -> str:
    """초를 '분:초' 또는 '시간:분' 형식으로 변환."""
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}분 {secs}초"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}시간 {minutes}분"

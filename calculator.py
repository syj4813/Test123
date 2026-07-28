# -*- coding: utf-8 -*-
"""
출발지/도착지(자연어 주소·장소명)와 탑승 인원수를 입력받아
자차 / 고속버스 / 철도 3가지 수단의 탄소·미세먼지 배출량과
철도 이용 시 환경 편익(자차·버스 대비 절감량)을 계산.

인원수(passengers)가 배출량에 미치는 영향:
- 자동차: 5인승 기준 배출계수라서, 인원수 자체가 아니라
  '몇 대가 필요한가'(ceil(인원수/5))에 따라만 배출량이 늘어난다.
  1~5명은 전부 동일한 배출량, 6명부터 2대분으로 증가.
- 고속버스/열차: 좌석 1인당 배출계수이므로 인원수에 정비례한다.

각 구간(leg)에는 실제 이동 경로 정보(route)도 함께 담긴다.
- 자차/버스/역·터미널 접근: 카카오 길찾기 API가 알려주는 주요 도로명 목록
- 철도: 다익스트라 최단경로 상의 경유역 목록 (정차역이 아니라 선로상 경로)
"""

from dataclasses import dataclass, field
from typing import Dict, List

from geocode import geocode
from road_distance import driving_distance_km, driving_route
from transit_distance import transit_route, TransitError, format_time
import train_api
import train_api_threading
from stations import nearest_stations
from terminals import nearest_terminals
from rail_distance import station_to_station_km
from emission_factors import compute_emission


@dataclass
class LegResult:
    mode: str                       # car / express_bus / ktx / mugunghwa / saemaul 등
    km: float
    co2_kg: float
    pm25_kg: float
    route: List[str] = field(default_factory=list)   # 주요 도로명 또는 경유역 목록
    duration_seconds: int = 0       # 소요시간(초), 0이면 미제공
    train_info: dict = field(default_factory=dict)   # 열차 정보 (편명, 출발시간, 도착시간 등)


@dataclass
class ModeResult:
    total_km: float
    total_co2_kg: float
    total_pm25_kg: float
    legs: list = field(default_factory=list)
    notes: list = field(default_factory=list)   # 근사치 사용 등 경고 메모
    total_duration_seconds: int = 0  # 전체 소요시간(초)


def _pick_best_station(candidates, origin_point):
    """직선거리 후보들에 대해 실제 도로거리를 계산, 최솟값 선택.
    candidates: [(name, lat, lng, line, straight_km), ...]
    반환: (name, lat, lng, line, road_km)
    """
    best = None
    for name, lat, lng, line, _ in candidates:
        try:
            road_km = driving_distance_km(origin_point, (lat, lng))
        except Exception:
            continue
        if best is None or road_km < best[4]:
            best = (name, lat, lng, line, road_km)
    if best is None:
        # 도로 API가 전부 실패하면 최근접(직선거리) 후보로 대체
        name, lat, lng, line, straight_km = candidates[0]
        best = (name, lat, lng, line, straight_km)
    return best


def _pick_best_terminal(candidates, origin_point):
    best = None
    for name, lat, lng, _ in candidates:
        try:
            road_km = driving_distance_km(origin_point, (lat, lng))
        except Exception:
            continue
        if best is None or road_km < best[3]:
            best = (name, lat, lng, road_km)
    if best is None:
        name, lat, lng, straight_km = candidates[0]
        best = (name, lat, lng, straight_km)
    return best


def _car_leg(mode_label, origin_pt, dest_pt, passengers):
    """자차로 이동하는 구간 하나를 계산 (거리 + 도로명 경로 + 배출량 + 소요시간)."""
    info = driving_route(origin_pt, dest_pt)   # {"km":..., "roads":[...], "duration_seconds":...}
    e = compute_emission("car", info["km"], passengers=passengers)
    return LegResult(
        mode_label, 
        info["km"], 
        e["co2_kg"], 
        e["pm25_kg"], 
        info["roads"],
        info.get("duration_seconds", 0)
    )


def compute_car(origin_pt, dest_pt, passengers: int = 1) -> ModeResult:
    leg = _car_leg("car", origin_pt, dest_pt, passengers)
    return ModeResult(leg.km, leg.co2_kg, leg.pm25_kg, [leg], [], leg.duration_seconds)


def compute_bus(origin_pt, dest_pt, passengers: int = 1) -> ModeResult:
    origin_terms = nearest_terminals(*origin_pt, k=3)
    dest_terms = nearest_terminals(*dest_pt, k=3)

    o_term = _pick_best_terminal(origin_terms, origin_pt)     # (name, lat, lng, km)
    d_term = _pick_best_terminal(dest_terms, dest_pt)

    leg1 = _car_leg("car(access→terminal)", origin_pt, (o_term[1], o_term[2]), passengers)
    leg2 = _car_leg("car(terminal→dest)", (d_term[1], d_term[2]), dest_pt, passengers)

    # 버스 터미널 간 대중교통 실제 소요시간 (버스 탑승)
    bus_duration_seconds = 0
    try:
        transit_info = transit_route((o_term[1], o_term[2]), (d_term[1], d_term[2]))
        bus_duration_seconds = transit_info.get("duration_seconds", 0)
        bus_km = transit_info.get("distance_m", 0) / 1000.0
    except TransitError:
        # 대중교통 API 실패 시 도로거리 근사 사용
        bus_info = driving_route((o_term[1], o_term[2]), (d_term[1], d_term[2]))
        bus_km = bus_info["km"]
        bus_duration_seconds = bus_info.get("duration_seconds", 0)

    e3 = compute_emission("express_bus", bus_km, passengers=passengers)
    leg_bus = LegResult(
        "express_bus", 
        bus_km, 
        e3["co2_kg"], 
        e3["pm25_kg"], 
        [],
        bus_duration_seconds
    )

    legs = [leg1, leg_bus, leg2]
    total_km = leg1.km + leg_bus.km + leg2.km
    total_co2 = leg1.co2_kg + leg_bus.co2_kg + leg2.co2_kg
    total_pm25 = leg1.pm25_kg + leg_bus.pm25_kg + leg2.pm25_kg
    total_duration = leg1.duration_seconds + leg_bus.duration_seconds + leg2.duration_seconds
    notes = [f"출발터미널: {o_term[0]}", f"도착터미널: {d_term[0]}"]
    return ModeResult(total_km, total_co2, total_pm25, legs, notes, total_duration)


RAIL_GRADES = ["ktx", "mugunghwa", "saemaul"]


def compute_rail(origin_pt, dest_pt, passengers: int = 1) -> Dict[str, ModeResult]:
    """세 등급(KTX/무궁화/새마을)을 모두 계산해서 {등급: ModeResult} 딕셔너리로 반환.

    출발/도착역 선정과 역간 실제거리는 등급과 무관하게 동일한 물리적 경로를
    쓰고(같은 선로를 다른 열차가 다닌다고 가정), 등급별 배출계수만 다르게
    적용한다. 즉 '이 구간에 그 등급 열차가 실제로 다니는지'는 확인하지 않는
    단순화된 비교용 수치다.
    """
    origin_stations = nearest_stations(*origin_pt, k=3)
    dest_stations = nearest_stations(*dest_pt, k=3)

    o_st = _pick_best_station(origin_stations, origin_pt)     # (name, lat, lng, line, km)
    d_st = _pick_best_station(dest_stations, dest_pt)

    leg_access1 = _car_leg("car(access→station)", origin_pt, (o_st[1], o_st[2]), passengers)
    leg_access2 = _car_leg("car(station→dest)", (d_st[1], d_st[2]), dest_pt, passengers)

    rail_km, is_approx, via_stations = station_to_station_km(
        o_st[0], o_st[1], o_st[2], d_st[0], d_st[1], d_st[2]
    )

    base_notes = [f"출발역: {o_st[0]}", f"도착역: {d_st[0]}"]
    if is_approx:
        base_notes.append(
            "⚠ 역간거리는 공식 데이터에 없어 직선거리×보정계수(근사값)입니다."
        )
    else:
        base_notes.append(f"경유 경로(선로 기준, 정차역 아님): {' - '.join(via_stations)}")

    # Threading으로 3개 등급 병렬 조회 (Streamlit 호환!)
    train_info_all = train_api_threading.get_all_train_info_parallel(o_st[0], d_st[0])
    
    results = {}
    for mode in RAIL_GRADES:
        # Threading 결과에서 소요시간 추출
        train_data = train_info_all.get(mode, {})
        train_duration_seconds = train_data.get("duration", 0)
        trains = train_data.get("trains", [])
        
        # API 실패 시 거리 기반 추정
        if train_duration_seconds == 0:
            speeds = {"ktx": 200, "saemaul": 80, "mugunghwa": 70}  # km/h
            train_duration_seconds = int(rail_km / speeds[mode] * 3600)
        
        # 가장 빠른 열차 정보 (첫 번째)
        best_train = trains[0] if trains else {}
        
        e3 = compute_emission(mode, rail_km, passengers=passengers)
        rail_leg = LegResult(
            mode, 
            rail_km, 
            e3["co2_kg"], 
            e3["pm25_kg"], 
            list(via_stations), 
            train_duration_seconds,
            best_train  # 열차 정보 포함
        )
        legs = [leg_access1, rail_leg, leg_access2]
        total_km = leg_access1.km + rail_km + leg_access2.km
        total_co2 = leg_access1.co2_kg + e3["co2_kg"] + leg_access2.co2_kg
        total_pm25 = leg_access1.pm25_kg + e3["pm25_kg"] + leg_access2.pm25_kg
        total_duration = leg_access1.duration_seconds + train_duration_seconds + leg_access2.duration_seconds
        results[mode] = ModeResult(total_km, total_co2, total_pm25, legs, list(base_notes), total_duration)

    return results


@dataclass
class ComparisonResult:
    car: ModeResult
    bus: ModeResult
    rail: Dict[str, ModeResult]   # {"ktx": ModeResult, "mugunghwa": ..., "saemaul": ...}

    def benefit_vs_car(self) -> Dict[str, Dict[str, float]]:
        return {
            mode: {
                "co2_kg_saved": self.car.total_co2_kg - r.total_co2_kg,
                "pm25_kg_saved": self.car.total_pm25_kg - r.total_pm25_kg,
            }
            for mode, r in self.rail.items()
        }

    def benefit_vs_bus(self) -> Dict[str, Dict[str, float]]:
        return {
            mode: {
                "co2_kg_saved": self.bus.total_co2_kg - r.total_co2_kg,
                "pm25_kg_saved": self.bus.total_pm25_kg - r.total_pm25_kg,
            }
            for mode, r in self.rail.items()
        }


def run(origin_query: str, dest_query: str, passengers: int = 1) -> ComparisonResult:
    o_lat, o_lng, o_addr = geocode(origin_query)
    d_lat, d_lng, d_addr = geocode(dest_query)
    origin_pt = (o_lat, o_lng)
    dest_pt = (d_lat, d_lng)

    car = compute_car(origin_pt, dest_pt, passengers)
    bus = compute_bus(origin_pt, dest_pt, passengers)
    rail = compute_rail(origin_pt, dest_pt, passengers)

    return ComparisonResult(car, bus, rail)

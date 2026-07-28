# -*- coding: utf-8 -*-
"""
실제 API 키 없이 계산 로직(배출계수 적용, 경로 합산, 편익 계산)만 검증하는 테스트.
geocode / driving_distance_km / driving_route 를 목(mock) 값으로 대체한다.
"""

import calculator


def fake_geocode(query, api_key=None):
    table = {
        "서울역 근처": (37.5546, 126.9707, "서울역 근처(mock)"),
        "부산 해운대": (35.1587, 129.1604, "부산 해운대(mock)"),
    }
    return table[query]


def _straight_km(origin, destination):
    import math
    lat1, lng1 = origin
    lat2, lng2 = destination
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def fake_driving_distance_km(origin, destination, api_key=None):
    return _straight_km(origin, destination) * 1.2  # 도로거리는 직선의 1.2배로 가정(모킹)


def fake_driving_route(origin, destination, api_key=None):
    km = _straight_km(origin, destination) * 1.2
    return {"km": km, "roads": ["OO대로(mock)", "OO고속도로(mock)"]}


def test_run():
    calculator.geocode = fake_geocode
    calculator.driving_distance_km = fake_driving_distance_km
    calculator.driving_route = fake_driving_route

    o_lat, o_lng, _ = fake_geocode("서울역 근처")
    d_lat, d_lng, _ = fake_geocode("부산 해운대")
    origin_pt, dest_pt = (o_lat, o_lng), (d_lat, d_lng)

    car = calculator.compute_car(origin_pt, dest_pt)
    bus = calculator.compute_bus(origin_pt, dest_pt)
    rail = calculator.compute_rail(origin_pt, dest_pt)   # {"ktx":.., "mugunghwa":.., "saemaul":..}

    print(f"자차: {car.total_km:.1f}km, CO2 {car.total_co2_kg:.2f}kg, 경로={car.legs[0].route}")
    print(f"버스: {bus.total_km:.1f}km, CO2 {bus.total_co2_kg:.2f}kg  ({bus.notes})")
    for mode, r in rail.items():
        rail_leg = next(l for l in r.legs if l.mode == mode)
        print(f"철도({mode}): {r.total_km:.1f}km, CO2 {r.total_co2_kg:.2f}kg  경유={rail_leg.route[:3]}...")

    assert car.total_km > 300  # 서울-부산 실제로 약 325km 내외
    assert car.legs[0].route == ["OO대로(mock)", "OO고속도로(mock)"]

    assert set(rail.keys()) == {"ktx", "mugunghwa", "saemaul"}
    for mode, r in rail.items():
        assert r.total_co2_kg < car.total_co2_kg, f"{mode}가 자차보다 배출량이 낮아야 함"
        rail_leg = next(l for l in r.legs if l.mode == mode)
        assert len(rail_leg.route) >= 2  # 최소 출발역~도착역
        assert rail_leg.route[0] == "서울"
        assert rail_leg.route[-1] == "부산"
    # KTX/새마을은 배출계수가 낮아 버스보다 유리하지만, 무궁화호는 1인당 배출계수가
    # 고속버스보다 오히려 높다 (0.08054 vs 0.05472 kg/km) - 이건 데이터상 사실이라
    # 버스보다 낮아야 한다고 단정하면 안 됨.
    assert rail["ktx"].total_co2_kg < bus.total_co2_kg
    assert rail["saemaul"].total_co2_kg < bus.total_co2_kg
    # 같은 물리적 거리라도 등급별 배출계수가 다르므로 총량도 달라야 함
    assert rail["ktx"].total_co2_kg != rail["mugunghwa"].total_co2_kg

    comp = calculator.ComparisonResult(car, bus, rail)
    benefit = comp.benefit_vs_car()
    assert set(benefit.keys()) == {"ktx", "mugunghwa", "saemaul"}
    assert benefit["ktx"]["co2_kg_saved"] > 0
    print(f"\n자차 대비 KTX 편익: CO2 {benefit['ktx']['co2_kg_saved']:.2f} kg 절감")

    print("\n✅ 모든 로직 테스트 통과")


def test_passenger_scaling():
    calculator.geocode = fake_geocode
    calculator.driving_distance_km = fake_driving_distance_km
    calculator.driving_route = fake_driving_route

    o_lat, o_lng, _ = fake_geocode("서울역 근처")
    d_lat, d_lng, _ = fake_geocode("부산 해운대")
    origin_pt, dest_pt = (o_lat, o_lng), (d_lat, d_lng)

    car_1 = calculator.compute_car(origin_pt, dest_pt, passengers=1)
    car_5 = calculator.compute_car(origin_pt, dest_pt, passengers=5)
    car_6 = calculator.compute_car(origin_pt, dest_pt, passengers=6)

    assert abs(car_1.total_co2_kg - car_5.total_co2_kg) < 1e-9
    assert abs(car_6.total_co2_kg - car_1.total_co2_kg * 2) < 1e-9

    rail_1 = calculator.compute_rail(origin_pt, dest_pt, passengers=1)
    rail_4 = calculator.compute_rail(origin_pt, dest_pt, passengers=4)
    for mode in ("ktx", "mugunghwa", "saemaul"):
        leg_1 = next(l for l in rail_1[mode].legs if l.mode == mode)
        leg_4 = next(l for l in rail_4[mode].legs if l.mode == mode)
        assert abs(leg_4.co2_kg - leg_1.co2_kg * 4) < 1e-9

    print("✅ 인원수 스케일링 테스트 통과 (자차 1~5명 동일, 6명부터 2배 / 철도 좌석분 인원수 정비례)")


if __name__ == "__main__":
    test_run()
    test_passenger_scaling()

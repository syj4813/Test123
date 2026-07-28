# -*- coding: utf-8 -*-
"""
사용법:
    export GOOGLE_MAPS_API_KEY="발급받은키"   (지오코딩용, 또는 config.py에 하드코딩)
    export KAKAO_REST_API_KEY="발급받은키"    (도로거리용, 또는 config.py에 하드코딩)
    python main.py

또는 코드에서:
    from calculator import run
    result = run("서울시 강남구 테헤란로 152", "부산 해운대 시그니엘", passengers=3)
"""

from calculator import run

_MODE_LABEL = {"ktx": "KTX", "mugunghwa": "무궁화호", "saemaul": "새마을호"}


def _print_mode(title, mr):
    print(f"\n[{title}]")
    print(f"  총 이동거리: {mr.total_km:.1f} km")
    print(f"  총 탄소배출: {mr.total_co2_kg:.3f} kg CO2eq")
    print(f"  총 미세먼지: {mr.total_pm25_kg * 1000:.2f} g PM2.5eq")
    for leg in mr.legs:
        print(f"    - {leg.mode}: {leg.km:.1f} km / "
              f"{leg.co2_kg:.3f} kg CO2 / {leg.pm25_kg*1000:.2f} g PM2.5")
        if leg.route:
            print(f"      경로: {' → '.join(leg.route)}")
    for note in mr.notes:
        print(f"  · {note}")


def _read_passengers() -> int:
    while True:
        raw = input("탑승 인원수 (숫자만, 예: 1): ").strip()
        try:
            n = int(raw)
            if n >= 1:
                return n
        except ValueError:
            pass
        print("  1 이상의 정수로 입력해주세요.")


def main():
    passengers = _read_passengers()
    origin = input("출발지 (정확한 주소나 장소명, 예: '서울시 강남구 테헤란로 152'): ").strip()
    dest = input("도착지 (정확한 주소나 장소명, 예: '부산 해운대 시그니엘'): ").strip()

    result = run(origin, dest, passengers=passengers)

    print(f"\n(탑승 인원: {passengers}명 기준)")
    _print_mode("자차", result.car)
    _print_mode("고속버스", result.bus)

    for mode in ("ktx", "mugunghwa", "saemaul"):
        _print_mode(f"철도 - {_MODE_LABEL[mode]}", result.rail[mode])

    b_car = result.benefit_vs_car()
    b_bus = result.benefit_vs_bus()

    print("\n[철도 이용 시 환경 편익 (등급별)]")
    for mode in ("ktx", "mugunghwa", "saemaul"):
        label = _MODE_LABEL[mode]
        bc, bb = b_car[mode], b_bus[mode]
        print(f"  {label}")
        print(f"    자차 대비: CO2 {bc['co2_kg_saved']:.3f} kg 절감, "
              f"PM2.5 {bc['pm25_kg_saved']*1000:.2f} g 절감")
        print(f"    고속버스 대비: CO2 {bb['co2_kg_saved']:.3f} kg 절감, "
              f"PM2.5 {bb['pm25_kg_saved']*1000:.2f} g 절감")


if __name__ == "__main__":
    main()

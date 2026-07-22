"""ETF 데이터 주기적 수집 스케줄러 모듈.

이 모듈은 `fetch_etf.py`의 `fetch_and_save_etf_data` 함수를 1분마다 주기적으로
호출하여 네이버 금융 ETF 목록 데이터를 최신 상태로 수집 및 저장합니다.
"""

import time
from datetime import datetime
from fetch_etf import fetch_and_save_etf_data


def run_scheduler(interval_seconds: int = 60) -> None:
    """지정한 시간 간격(초)마다 ETF 데이터를 수집하는 스케줄러 루프를 실행합니다.

    Args:
        interval_seconds (int): 수집 주기(초 단위). 기본값은 60초(1분).
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ETF 데이터 수집 스케줄러가 시작되었습니다. (주기: {interval_seconds}초)")
    
    while True:
        try:
            fetch_and_save_etf_data()
        except Exception as e:
            print(f"[Error] ETF 데이터 수집 중 오류 발생: {e}")
        
        # 지정된 간격만큼 대기
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_scheduler(interval_seconds=60)

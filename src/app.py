"""실시간 네이버 ETF 종합 EDA 대시보드 애플리케이션.

이 모듈은 네이버 금융 Sise API에서 실시간 ETF 항목 데이터를 직접 조회하여
파일 저장 없이 메모리 상에서 종합적인 탐색적 데이터 분석(EDA)을 수행하고,
Streamlit과 Plotly를 통해 시각화 대시보드를 제공합니다.
"""

import os
import json
from datetime import datetime
from typing import Tuple, Dict, Any, Optional
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ================= ============================================================
# 페이지 설정 및 테마 지정
# ==============================================================================
st.set_page_config(
    page_title="네이버 ETF 실시간 EDA 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS 스타일링 (모던 피콕 블루/다크 스타일)
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 4px solid #1E88E5;
    }
</style>
""", unsafe_allow_html=True)


# ================= ============================================================
# 데이터 수집 및 전처리 함수
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_realtime_etf_data() -> Tuple[pd.DataFrame, str]:
    """네이버 금융 API로부터 실시간 ETF 데이터를 조회하고 전처리합니다.

    Returns:
        Tuple[pd.DataFrame, str]: 전처리된 데이터프레임과 수집 시각 문자열.

    Raises:
        requests.RequestException: API 호출 실패 시 발생.
    """
    url: str = "https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0&targetColumn=market_sum&sortOrder=desc"
    headers: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    
    # API 요청 실행
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    response.encoding = 'euc-kr'
    
    data: Dict[str, Any] = response.json()
    items: list[dict] = data.get("result", {}).get("etfItemList", [])
    
    if not items:
        return pd.DataFrame(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    df: pd.DataFrame = pd.DataFrame(items)
    fetch_time: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 데이터 타입 캐스팅 및 파생 변수 생성
    df['itemcode'] = df['itemcode'].astype(str)
    df['nowVal'] = pd.to_numeric(df['nowVal'], errors='coerce')
    df['changeVal'] = pd.to_numeric(df['changeVal'], errors='coerce')
    df['changeRate'] = pd.to_numeric(df['changeRate'], errors='coerce')
    df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
    df['marketSum'] = pd.to_numeric(df['marketSum'], errors='coerce')  # 억원 단위
    df['quant'] = pd.to_numeric(df['quant'], errors='coerce')          # 거래량(주)
    df['amonut'] = pd.to_numeric(df['amonut'], errors='coerce')        # 거래대금(백만원)
    df['threeMonthEarnRate'] = pd.to_numeric(df['threeMonthEarnRate'], errors='coerce')

    # 1. 시가총액 (조 원 단위 파생변수)
    df['marketSum_trillion'] = (df['marketSum'] / 10000).round(2)
    
    # 2. 거래대금 (억 원 단위 파생변수)
    df['amount_hundred_million'] = (df['amonut'] / 100).round(2)
    
    # 3. NAV 대비 괴리율(%) = (현재가 - NAV) / NAV * 100
    df['disparityRate'] = np.where(
        (df['nav'].notnull()) & (df['nav'] > 0),
        ((df['nowVal'] - df['nav']) / df['nav'] * 100).round(2),
        np.nan
    )

    # 4. 등락 구분 라벨
    conditions = [
        (df['changeRate'] > 0),
        (df['changeRate'] < 0),
        (df['changeRate'] == 0)
    ]
    choices = ['상승 🔺', '하락 🔻', '보합 ➖']
    df['changeTrend'] = np.select(conditions, choices, default='미상')

    # 5. ETF 탭 코드 매핑
    tab_code_map = {
        1: '국내 대표지수',
        2: '국내 업종/테마',
        3: '국내 파생',
        4: '해외 주식',
        5: '원자재/원자재파생',
        6: '채권/금리',
        7: '기타'
    }
    df['category'] = df['etfTabCode'].map(tab_code_map).fillna('기타/미분류')

    return df, fetch_time


# ================= ============================================================
# 대시보드 메인 레이아웃
# ==============================================================================
def main() -> None:
    """Streamlit 대시보드의 메인 실행 함수입니다."""
    
    # 1. 사이드바 구성
    st.sidebar.title("🔍 대시보드 설정 및 필터")
    
    # 데이터 로딩
    try:
        with st.spinner("네이버 금융 API에서 실시간 ETF 데이터 로딩 중..."):
            df, fetch_time = fetch_realtime_etf_data()
    except Exception as e:
        st.error(f"실시간 데이터 로딩 중 오류가 발생했습니다: {e}")
        return

    if df.empty:
        st.warning("수집된 ETF 데이터가 없습니다.")
        return

    # 새로고침 버튼
    if st.sidebar.button("🔄 데이터 즉시 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.caption(f"⏱️ 마지막 수집 시간: **{fetch_time}**")
    st.sidebar.markdown("---")

    # 사이드바 필터링
    st.sidebar.subheader("📌 ETF 필터링")
    
    # 카테고리 필터
    categories = ['전체'] + sorted(list(df['category'].unique()))
    selected_category = st.sidebar.selectbox("ETF 카테고리 선택", categories)
    
    # 시가총액 필터 (억원)
    min_market_sum, max_market_sum = int(df['marketSum'].min()), int(df['marketSum'].max())
    selected_market_range = st.sidebar.slider(
        "시가총액 범위 (억 원)",
        min_value=min_market_sum,
        max_value=max_market_sum,
        value=(min_market_sum, max_market_sum),
        step=500
    )

    # 검색어 필터
    search_keyword = st.sidebar.text_input("ETF 종목명/코드 검색", "").strip()

    # 데이터 필터링 적용
    filtered_df = df.copy()
    if selected_category != '전체':
        filtered_df = filtered_df[filtered_df['category'] == selected_category]
    
    filtered_df = filtered_df[
        (filtered_df['marketSum'] >= selected_market_range[0]) & 
        (filtered_df['marketSum'] <= selected_market_range[1])
    ]

    if search_keyword:
        filtered_df = filtered_df[
            filtered_df['itemname'].str.contains(search_keyword, case=False, na=False) |
            filtered_df['itemcode'].str.contains(search_keyword, case=False, na=False)
        ]

    # 2. 메인 헤더
    st.markdown('<div class="main-header">📈 네이버 ETF 실시간 EDA 대시보드</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">별도 파일 저장 없이 메모리 상에서 실시간 수집된 <b>{len(df)}개 ETF 종목</b>의 종합 EDA 리포트를 조회합니다.</div>', unsafe_allow_html=True)

    # 3. 주요 KPI 메트릭 카드
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_etf_cnt = len(filtered_df)
    total_market_cap_trillion = (filtered_df['marketSum'].sum() / 10000).round(2)
    total_trading_amount_hm = (filtered_df['amonut'].sum() / 100).round(2)
    up_cnt = (filtered_df['changeRate'] > 0).sum()
    down_cnt = (filtered_df['changeRate'] < 0).sum()

    col1.metric("조회 종목 수", f"{total_etf_cnt:,} 개")
    col2.metric("총 시가총액", f"{total_market_cap_trillion:,.2f} 조 원")
    col3.metric("총 거래대금", f"{total_trading_amount_hm:,.2f} 억 원")
    col4.metric("상승 종목 🔺", f"{up_cnt:,} 개", delta=f"{up_cnt/total_etf_cnt*100:.1f}%" if total_etf_cnt > 0 else "0%")
    col5.metric("하락 종목 🔻", f"{down_cnt:,} 개", delta=f"-{down_cnt/total_etf_cnt*100:.1f}%" if total_etf_cnt > 0 else "0%", delta_color="inverse")

    st.markdown("---")

    # 4. 탭 기반 상세 EDA 시각화
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 개요 & 랭킹", 
        "📈 시가총액 & 거래량 EDA", 
        "🔄 수익률 & 괴리율 분석", 
        "📋 실시간 데이터 Explorer"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: 개요 & 랭킹
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("🏆 주요 랭킹 분석 (Top 10)")
        
        r_col1, r_col2 = st.columns(2)
        
        with r_col1:
            st.markdown("##### 💎 시가총액 Top 10 ETF")
            top10_market_cap = filtered_df.nlargest(10, 'marketSum')
            fig_market_cap = px.bar(
                top10_market_cap,
                x='marketSum_trillion',
                y='itemname',
                orientation='h',
                text='marketSum_trillion',
                color='marketSum_trillion',
                color_continuous_scale='Blues',
                labels={'marketSum_trillion': '시가총액 (조 원)', 'itemname': 'ETF 종목명'},
                title="시가총액 상위 10개 종목"
            )
            fig_market_cap.update_layout(yaxis=dict(autorange="reversed"), height=400, showlegend=False)
            st.plotly_chart(fig_market_cap, use_container_width=True)

        with r_col2:
            st.markdown("##### 🔥 거래대금 Top 10 ETF")
            top10_amount = filtered_df.nlargest(10, 'amonut')
            fig_amount = px.bar(
                top10_amount,
                x='amount_hundred_million',
                y='itemname',
                orientation='h',
                text='amount_hundred_million',
                color='amount_hundred_million',
                color_continuous_scale='Oranges',
                labels={'amount_hundred_million': '거래대금 (억 원)', 'itemname': 'ETF 종목명'},
                title="거래대금 상위 10개 종목"
            )
            fig_amount.update_layout(yaxis=dict(autorange="reversed"), height=400, showlegend=False)
            st.plotly_chart(fig_amount, use_container_width=True)

        st.markdown("---")
        r_col3, r_col4 = st.columns(2)
        
        with r_col3:
            st.markdown("##### 🚀 당일 등락률 상위 10 ETF")
            top10_rise = filtered_df.nlargest(10, 'changeRate')
            fig_rise = px.bar(
                top10_rise,
                x='changeRate',
                y='itemname',
                orientation='h',
                text='changeRate',
                color='changeRate',
                color_continuous_scale='Reds',
                labels={'changeRate': '등락률 (%)', 'itemname': 'ETF 종목명'},
                title="등락률 상위 (상승률 🔝)"
            )
            fig_rise.update_layout(yaxis=dict(autorange="reversed"), height=400, showlegend=False)
            st.plotly_chart(fig_rise, use_container_width=True)

        with r_col4:
            st.markdown("##### 📉 당일 등락률 하위 10 ETF")
            top10_fall = filtered_df.nsmallest(10, 'changeRate')
            fig_fall = px.bar(
                top10_fall,
                x='changeRate',
                y='itemname',
                orientation='h',
                text='changeRate',
                color='changeRate',
                color_continuous_scale='Purples_r',
                labels={'changeRate': '등락률 (%)', 'itemname': 'ETF 종목명'},
                title="등락률 하위 (하락률 🔻)"
            )
            fig_fall.update_layout(yaxis=dict(autorange="reversed"), height=400, showlegend=False)
            st.plotly_chart(fig_fall, use_container_width=True)

    # --------------------------------------------------------------------------
    # TAB 2: 시가총액 & 거래량 EDA
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("📈 시가총액 및 거래량 관계 분석")
        
        c1, c2 = st.columns([6, 4])
        
        with c1:
            st.markdown("##### 📍 시가총액 vs 거래대금 산점도 (Scatter Plot)")
            fig_scatter = px.scatter(
                filtered_df,
                x='marketSum_trillion',
                y='amount_hundred_million',
                size='quant',
                color='changeRate',
                hover_name='itemname',
                hover_data=['itemcode', 'nowVal', 'changeRate', 'category'],
                color_continuous_scale='RdBu_r',
                color_continuous_midpoint=0,
                labels={
                    'marketSum_trillion': '시가총액 (조 원)',
                    'amount_hundred_million': '거래대금 (억 원)',
                    'changeRate': '등락률 (%)'
                },
                title="시가총액 vs 거래대금 (버블 크기: 거래량)"
            )
            fig_scatter.update_layout(height=500)
            st.plotly_chart(fig_scatter, use_container_width=True)

        with c2:
            st.markdown("##### 📂 ETF 카테고리별 시가총액 비중")
            cat_summary = filtered_df.groupby('category')['marketSum_trillion'].sum().reset_index()
            fig_pie = px.pie(
                cat_summary,
                values='marketSum_trillion',
                names='category',
                hole=0.4,
                title="카테고리별 시가총액 구성비",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")
        st.markdown("##### 📊 시가총액 분포 (히스토그램 및 Boxplot)")
        
        fig_box = px.box(
            filtered_df,
            x='category',
            y='marketSum',
            color='category',
            points="all",
            hover_name='itemname',
            labels={'marketSum': '시가총액 (억 원)', 'category': '카테고리'},
            title="카테고리별 시가총액 분포 (로그 스케일 적용 권장)"
        )
        fig_box.update_layout(yaxis_type="log", height=450, showlegend=False)
        st.plotly_chart(fig_box, use_container_width=True)

    # --------------------------------------------------------------------------
    # TAB 3: 수익률 & 괴리율 분석
    # --------------------------------------------------------------------------
    with tab3:
        st.subheader("🔄 3개월 수익률 및 NAV 괴리율 분석")
        
        p1, p2 = st.columns(2)
        
        with p1:
            st.markdown("##### 📊 3개월 수익률 분포")
            fig_earn_hist = px.histogram(
                filtered_df.dropna(subset=['threeMonthEarnRate']),
                x='threeMonthEarnRate',
                nbins=40,
                color='changeTrend',
                color_discrete_map={'상승 🔺': '#ef5350', '하락 🔻': '#42a5f5', '보합 ➖': '#bdbdbd'},
                labels={'threeMonthEarnRate': '3개월 수익률 (%)'},
                title="3개월 수익률 분포 히스토그램"
            )
            fig_earn_hist.update_layout(height=400)
            st.plotly_chart(fig_earn_hist, use_container_width=True)

        with p2:
            st.markdown("##### ⚖️ NAV 대비 괴리율(%) 분포")
            fig_disp_hist = px.histogram(
                filtered_df.dropna(subset=['disparityRate']),
                x='disparityRate',
                nbins=50,
                labels={'disparityRate': 'NAV 괴리율 (%)'},
                title="NAV 괴리율 분포 (0% 중심)",
                color_discrete_sequence=['#26a69a']
            )
            fig_disp_hist.update_layout(height=400)
            st.plotly_chart(fig_disp_hist, use_container_width=True)

        st.markdown("---")
        st.markdown("##### ⚠️ 괴리율 주의 종목 감지 (절대값 괴리율 상위 10개)")
        
        temp_df = filtered_df.dropna(subset=['disparityRate']).copy()
        temp_df['abs_disparity'] = temp_df['disparityRate'].abs()
        high_disparity_df = temp_df.nlargest(10, 'abs_disparity')[
            ['itemcode', 'itemname', 'category', 'nowVal', 'nav', 'disparityRate', 'changeRate']
        ]
        
        st.dataframe(
            high_disparity_df.style.format({
                'nowVal': '{:,.0f}원',
                'nav': '{:,.2f}원',
                'disparityRate': '{:+.2f}%',
                'changeRate': '{:+.2f}%'
            }).background_gradient(subset=['disparityRate'], cmap='vlag'),
            use_container_width=True
        )

    # --------------------------------------------------------------------------
    # TAB 4: 실시간 데이터 Explorer
    # --------------------------------------------------------------------------
    with tab4:
        st.subheader("📋 전체 ETF 실시간 데이터 조율 Explorer")
        
        st.write(f"현재 조건에 해당하는 총 **{len(filtered_df)}**개의 ETF 종목이 있습니다.")
        
        display_columns = [
            'itemcode', 'itemname', 'category', 'nowVal', 'changeVal', 'changeRate', 
            'nav', 'disparityRate', 'marketSum_trillion', 'amount_hundred_million', 
            'quant', 'threeMonthEarnRate'
        ]
        
        col_rename_map = {
            'itemcode': '종목코드',
            'itemname': 'ETF 종목명',
            'category': '카테고리',
            'nowVal': '현재가(원)',
            'changeVal': '전일대비(원)',
            'changeRate': '등락률(%)',
            'nav': 'NAV(원)',
            'disparityRate': '괴리율(%)',
            'marketSum_trillion': '시가총액(조원)',
            'amount_hundred_million': '거래대금(억원)',
            'quant': '거래량(주)',
            'threeMonthEarnRate': '3개월수익률(%)'
        }
        
        explorer_df = filtered_df[display_columns].rename(columns=col_rename_map)
        
        st.dataframe(
            explorer_df,
            use_container_width=True,
            height=500
        )
        
        # CSV 다운로드 버튼 (메모리 상에서 생성)
        csv_data = explorer_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 현재 필터링된 데이터 CSV 다운로드",
            data=csv_data,
            file_name=f"etf_realtime_eda_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )


if __name__ == "__main__":
    main()

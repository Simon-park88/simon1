import streamlit as st
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("💧 필요 칠러 용량 산정")
st.info("저장된 챔버 사양을 불러오거나, 필요 유량(LPM)을 직접 입력하여 칠러 용량 및 연간 전력량을 계산할 수 있습니다.")

# --- 1. 계산 함수 정의 ---
def calculate_heat_from_lpm(lpm, delta_t):
    """LPM과 온도차로 필요 열량(kcal/h)을 계산하는 함수"""
    return lpm * delta_t * 60

# --- 2. st.session_state 초기화 ---
if 'chiller_capacity_kcal' not in st.session_state:
    st.session_state.chiller_capacity_kcal = 10000.0
if 'chiller_power_kw' not in st.session_state:
    st.session_state.chiller_power_kw = 5.0
if 'chamber_count_for_chiller' not in st.session_state:
    st.session_state.chamber_count_for_chiller = 10
if 'operating_hours' not in st.session_state:
    st.session_state.operating_hours = 8760
if 'operation_rate' not in st.session_state:
    st.session_state.operation_rate = 80


# --- 3. 계산 방식 선택 UI ---
calc_method = st.selectbox(
    "계산 방식을 선택하세요",
    ("자동 계산 (저장된 챔버 사양 사용)", "수동 계산 (직접 입력)")
)
st.markdown("---")

heat_per_chamber_kcal = 0

# --- 4. 선택된 방식에 따른 계산 로직 (수정된 부분) ---
if calc_method == "자동 계산 (저장된 챔버 사양 사용)":
    st.subheader("1. 저장된 챔버 사양으로 자동 계산")
    
    chamber_specs = st.session_state.get("chamber_specs", {})

    if not chamber_specs:
        st.warning("⚠️ 먼저 '챔버 설정 및 계산' 페이지에서 챔버 사양을 저장해주세요.")
    else:
        cooling_type = chamber_specs.get('cooling_type', '공냉식')
        
        if cooling_type == '수냉식':
            st.info("저장된 챔버 사양은 '수냉식'입니다. 해당 사양 기준으로 챔버 1대의 필요 열량을 계산합니다.")
            
            # ★★★★★ 수정된 부분: 저장된 최종 발열량 값을 직접 가져옴 ★★★★★
            total_heat_to_reject_w = chamber_specs.get('total_heat_to_reject_w', 0)
            
            # W를 kcal/h로 변환 (1W = 0.86 kcal/h)
            heat_per_chamber_kcal = total_heat_to_reject_w * 0.86
            
            st.metric("챔버 1대 기준 필요 열량", f"{heat_per_chamber_kcal:,.0f} kcal/h")
        else:
            st.warning("⚠️ 저장된 챔버 사양의 냉각 방식이 '공냉식'입니다. 칠러 계산은 '수냉식'일 때만 유효합니다.")

elif calc_method == "수동 계산 (직접 입력)":
    st.subheader("1. 필요 열량 수동 계산")
    
    col1, col2 = st.columns(2)
    with col1:
        manual_lpm = st.number_input("챔버 1대 필요 유량 (LPM)", min_value=0.0, value=100.0, step=1.0)
    with col2:
        manual_delta_t = st.number_input("냉각수 입출수 온도차 (ΔT, °C)", min_value=0.1, value=5.0, step=0.1, format="%.1f")
        
    heat_per_chamber_kcal = calculate_heat_from_lpm(manual_lpm, manual_delta_t)
    
    st.metric("챔버 1대 기준 필요 열량", f"{heat_per_chamber_kcal:,.0f} kcal/h")

# --- 5. 운용 조건 설정 ---
st.markdown("---")
st.subheader("2. 운용 조건 설정")
col1, col2 = st.columns(2)
with col1:
    st.number_input("챔버 수량 (대)", min_value=1, step=1, key='chamber_count_for_chiller')
    st.number_input("총 운용 시간 (H)", min_value=1, step=1, key='operating_hours')
with col2:
    st.slider("동작률 (%)", min_value=0, max_value=100, key='operation_rate', help="총 운용 시간 중 칠러가 실제로 가동되는 시간의 비율입니다.")

# 총 필요 열량 계산
total_required_heat_kcal = heat_per_chamber_kcal * st.session_state.chamber_count_for_chiller
if total_required_heat_kcal > 0:
    st.success(f"총 필요 열량 (챔버 {st.session_state.chamber_count_for_chiller}대): **{total_required_heat_kcal:,.0f} kcal/h**")


# --- 6. 필요 칠러 대수 계산 UI 및 로직 ---
st.markdown("---")
st.subheader("3. 필요 칠러 대수 및 연간 전력량 계산")

if total_required_heat_kcal > 0:
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("단일 칠러 냉각 용량 (kcal/h)", min_value=1.0, key='chiller_capacity_kcal', format="%.0f")
    with col2:
        st.number_input("단일 칠러 소비 전력 (kW)", min_value=0.1, key='chiller_power_kw', format="%.2f")

    if st.session_state.chiller_capacity_kcal > 0:
        required_chillers = math.ceil(total_required_heat_kcal / st.session_state.chiller_capacity_kcal)
        
        chiller_efficiency_factor = st.session_state.chiller_power_kw / st.session_state.chiller_capacity_kcal
        
        peak_chiller_power = total_required_heat_kcal * chiller_efficiency_factor
        average_chiller_power = peak_chiller_power * (st.session_state.operation_rate / 100.0)
        annual_kwh = average_chiller_power * st.session_state.operating_hours

        st.markdown("---")
        st.subheader("✅ 최종 계산 결과")
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("필요 칠러 대수", f"{required_chillers} 대", help="총 필요 열량을 감당하기 위해 설치해야 하는 최소 칠러 수량입니다.")
        with col_res2:
            st.metric("최대 소비 전력 (Peak)", f"{peak_chiller_power:.2f} kW", help="칠러가 가동되는 순간의 최대 소비 전력입니다. 설비 용량 산정의 기준이 됩니다.")
        
        col_res3, col_res4 = st.columns(2)
        with col_res3:
            st.metric("평균 소비 전력 (수용률 적용)", f"{average_chiller_power:.2f} kW", help="동작률을 고려한 시간당 평균 소비 전력입니다.")
        with col_res4:
            st.metric("연간 총 전력량", f"{annual_kwh:,.0f} kWh", help="연간 총 에너지 소비량으로, 전기 요금 예측의 기준이 됩니다.")

    else:
        st.warning("칠러의 냉각 용량은 0보다 커야 합니다.")
else:
    st.info("필요 열량을 먼저 계산해주세요.")

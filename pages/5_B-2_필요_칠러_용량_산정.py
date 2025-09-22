import streamlit as st
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("💧 필요 칠러 용량 산정")
st.info("저장된 챔버 사양을 불러오거나, 필요 유량(LPM)을 직접 입력하여 칠러 용량 및 연간 전력량을 계산할 수 있습니다.")

# --- 1. st.session_state 초기화 및 콜백 함수 ---
CHILLER_DEFAULTS = {
    'chiller_capacity_kcal': 10000.0,
    'chiller_power_kw': 5.0,
    'chamber_count_for_chiller': 10,
    'operating_hours': 8760,
    'operation_rate': 80,
    'calc_to_load': "선택하세요" # 불러오기 UI용
}

def initialize_state():
    """세션 상태 초기화"""
    if 'saved_chiller_calcs' not in st.session_state:
        st.session_state.saved_chiller_calcs = {}
    # 다른 페이지의 데이터를 읽기 위해 초기화
    if 'saved_chamber_specs' not in st.session_state:
        st.session_state.saved_chamber_specs = {}
        
    for key, value in CHILLER_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

def load_chiller_calc_callback():
    """선택된 칠러 계산 결과를 session_state로 불러오는 콜백 함수"""
    calc_name = st.session_state.calc_to_load
    if calc_name != "선택하세요" and calc_name in st.session_state.saved_chiller_calcs:
        loaded_data = st.session_state.saved_chiller_calcs[calc_name]
        for key, value in loaded_data.items():
            # 저장된 데이터 중 UI 입력값과 관련된 것들만 업데이트
            if key in CHILLER_DEFAULTS:
                st.session_state[key] = value
        st.success(f"'{calc_name}' 계산 결과를 성공적으로 불러왔습니다!")

initialize_state()

# --- 2. 계산 함수 정의 ---
def calculate_heat_from_lpm(lpm, delta_t):
    """LPM과 온도차로 필요 열량(kcal/h)을 계산하는 함수"""
    return lpm * delta_t * 60

# --- 3. 계산 방식 선택 UI ---
calc_method = st.selectbox(
    "계산 방식을 선택하세요",
    ("자동 계산 (저장된 챔버 사양 사용)", "수동 계산 (직접 입력)")
)
st.markdown("---")

heat_per_chamber_kcal = 0

# --- 4. 선택된 방식에 따른 계산 로직 ---
if calc_method == "자동 계산 (저장된 챔버 사양 사용)":
    st.subheader("1. 저장된 챔버 사양으로 자동 계산")
    
    saved_chamber_specs = st.session_state.saved_chamber_specs

    if not saved_chamber_specs:
        st.warning("⚠️ 먼저 '챔버 사양 정의 및 계산' 페이지에서 챔버 사양을 저장해주세요.")
    else:
        selected_chamber_spec_name = st.selectbox("계산에 사용할 챔버 사양을 선택하세요", options=list(saved_chamber_specs.keys()))
        chamber_specs = saved_chamber_specs[selected_chamber_spec_name]
        
        cooling_type = chamber_specs.get('cooling_type', '공냉식')
        
        if cooling_type == '수냉식':
            max_heat_rejection_w = chamber_specs.get('max_heat_rejection_w', 0)
            
            if max_heat_rejection_w > 0:
                heat_per_chamber_kcal = max_heat_rejection_w * 0.86
                st.info(f"선택된 '{selected_chamber_spec_name}' 사양의 최대 냉각 부하(최저 온도 기준)로 자동 계산합니다.")
                st.metric("챔버 1대 기준 필요 열량", f"{heat_per_chamber_kcal:,.0f} kcal/h")
            else:
                st.warning("⚠️ 선택된 챔버 사양에 유효한 냉각 부하 정보가 없습니다. '챔버 사양' 페이지에서 다시 저장해주세요.")
        else:
            st.warning("⚠️ 선택된 챔버 사양의 냉각 방식이 '공냉식'입니다. 칠러 계산은 '수냉식'일 때만 유효합니다.")

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

total_required_heat_kcal = heat_per_chamber_kcal * st.session_state.chamber_count_for_chiller
if total_required_heat_kcal > 0:
    st.success(f"총 필요 열량 (챔버 {st.session_state.chamber_count_for_chiller}대): **{total_required_heat_kcal:,.0f} kcal/h**")

# --- 6. 필요 칠러 대수 계산 UI 및 로직 ---
st.markdown("---")
st.subheader("3. 필요 칠러 대수 및 연간 전력량 계산")

peak_chiller_power = 0
average_chiller_power = 0
annual_kwh = 0

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
        col_res1.metric("필요 칠러 대수", f"{required_chillers} 대", help="총 필요 열량을 감당하기 위해 설치해야 하는 최소 칠러 수량입니다.")
        col_res2.metric("최대 소비 전력 (Peak)", f"{peak_chiller_power:.2f} kW", help="칠러가 가동되는 순간의 최대 소비 전력입니다. 설비 용량 산정의 기준이 됩니다.")
        
        col_res3, col_res4 = st.columns(2)
        col_res3.metric("평균 소비 전력 (동작률 적용)", f"{average_chiller_power:.2f} kW", help="동작률을 고려한 시간당 평균 소비 전력입니다. 이 값이 전기 요금 계산의 Peak 전력으로 사용됩니다.")
        col_res4.metric("연간 총 전력량", f"{annual_kwh:,.0f} kWh", help="연간 총 에너지 소비량으로, 전기 요금 예측의 기준이 됩니다.")
    else:
        st.warning("칠러의 냉각 용량은 0보다 커야 합니다.")
else:
    st.info("필요 열량을 먼저 계산해주세요.")

# --- 7. 설정값 저장 버튼 ---
st.markdown("---")
with st.form("chiller_save_form"):
    chiller_save_name = st.text_input("저장할 계산 결과의 이름을 입력하세요")
    submitted = st.form_submit_button("💾 현재 계산 결과 저장")
    if submitted:
        if not chiller_save_name:
            st.warning("저장할 이름을 입력해주세요.")
        elif total_required_heat_kcal <= 0:
            st.warning("저장할 유효한 계산 결과가 없습니다.")
        else:
            data_to_save = {key: st.session_state[key] for key in CHILLER_DEFAULTS}
            # ★★★★★ 수정된 부분: peak_chiller_power 키에 '평균 소비 전력'을 저장 ★★★★★
            data_to_save['peak_chiller_power'] = average_chiller_power
            data_to_save['annual_kwh'] = annual_kwh
            
            st.session_state.saved_chiller_calcs[chiller_save_name] = data_to_save
            st.success(f"'{chiller_save_name}' 이름으로 현재 계산 결과가 저장되었습니다 ✅")

# --- 8. 저장된 사양 관리 ---
st.markdown("---")
st.subheader("📂 저장된 계산 결과 관리")
if not st.session_state.saved_chiller_calcs:
    st.info("저장된 계산 결과가 없습니다.")
else:
    col_load1, col_load2, col_load3 = st.columns([0.6, 0.2, 0.2])
    with col_load1:
        st.selectbox("불러올 계산 결과를 선택하세요", 
                     options=["선택하세요"] + list(st.session_state.saved_chiller_calcs.keys()),
                     key="calc_to_load")
    with col_load2:
        st.button("📥 선택한 결과 불러오기", on_click=load_chiller_calc_callback, use_container_width=True)
    with col_load3:
        if st.button("⚠️ 선택한 결과 삭제", use_container_width=True):
            calc_name_to_delete = st.session_state.calc_to_load
            if calc_name_to_delete in st.session_state.saved_chiller_calcs:
                del st.session_state.saved_chiller_calcs[calc_name_to_delete]
                st.session_state.calc_to_load = "선택하세요"
                st.success(f"'{calc_name_to_delete}' 계산 결과를 삭제했습니다.")
                st.rerun()
            else:
                st.warning("삭제할 계산 결과를 먼저 선택해주세요.")


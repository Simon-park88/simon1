import streamlit as st
import numpy as np
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("🔌 챔버 사양 정의 및 계산")
st.info("챔버의 상세 사양을 입력하여 소비 전력과 필요 냉각 용량을 계산합니다. 저장된 사양은 칠러 및 전기 요금 산출 페이지에서 사용됩니다.")

# --- 1. st.session_state 초기화 ---
CHAMBER_DEFAULTS = {
    'chamber_w': 1000, 'chamber_d': 1000, 'chamber_h': 1000,
    'insulation_type': '우레탄폼', 'insulation_thickness': 100,
    'sus_thickness': 1.2,
    'min_temp_spec': -10.0, 'max_temp_spec': 60.0, 'target_temp': -10.0,
    'outside_temp': 25.0,
    'fan_motor_load': 2.0, 'fan_soak_factor': 30,
    'min_soak_load_factor': 30,
    'load_type': '없음', 'num_cells': 4, 'cell_size': '211Ah (현대차 규격)',
    'ramp_rate': 1.0,
    'refrigeration_system': '1원 냉동',
    'actual_hp_1stage': 5.0, 'actual_rated_power_1stage': 3.5,
    'actual_hp_2stage_h': 3.0, 'actual_hp_2stage_l': 2.0,
    'actual_rated_power_2stage_h': 2.0, 'actual_rated_power_2stage_l': 1.5,
    'heater_capacity': 5.0,
    'cooling_type': '수냉식', 'cooling_water_delta_t': 5.0,
    'cooling_water_supply_temp': 20.0,
    'safety_factor': 1.5,
    'spec_to_load': "선택하세요" # 불러오기 UI용
}

def initialize_state():
    """앱 세션에서 사용할 모든 변수들의 기본값을 설정합니다."""
    if 'saved_chamber_specs' not in st.session_state:
        st.session_state.saved_chamber_specs = {}

    for key, value in CHAMBER_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_state()

# --- 2. 콜백 함수 정의 ---
def update_fan_recommendation():
    """챔버 크기가 변경될 때 팬/모터 부하 추천값을 업데이트합니다."""
    volume_m3 = (st.session_state.chamber_w * st.session_state.chamber_d * st.session_state.chamber_h) / 1_000_000_000
    if volume_m3 < 1: st.session_state.fan_motor_load = 0.5
    elif 1 <= volume_m3 < 8: st.session_state.fan_motor_load = 1.5
    else: st.session_state.fan_motor_load = 2.5

def load_chamber_spec_callback():
    """선택된 챔버 사양을 session_state로 불러오는 콜백 함수 (에러 방지)"""
    spec_name = st.session_state.spec_to_load
    if spec_name != "선택하세요" and spec_name in st.session_state.saved_chamber_specs:
        loaded_data = st.session_state.saved_chamber_specs[spec_name]
        for key, value in loaded_data.items():
            if key in CHAMBER_DEFAULTS:
                st.session_state[key] = value
        st.success(f"'{spec_name}' 사양을 성공적으로 불러왔습니다!")

# --- 3. 데이터 정의 ---
K_VALUES = {"우레탄폼": 0.023, "글라스울": 0.040, "세라크울": 0.150}
DENSITY_SUS = 7930
COP_TABLE_1STAGE = {10: 4.0, 0: 3.0, -10: 2.2, -20: 1.5, -25: 1.2}
COP_TABLE_2STAGE = {-20: 2.5, -30: 2.0, -40: 1.5, -50: 1.1, -60: 0.8, -70: 0.5}
WATT_TO_KCAL_H = 0.86
COOLING_TEMP_CORRECTION_FACTORS = {7: 0.9, 15: 1.0, 25: 1.15, 30: 1.25}

# --- 4. UI 구성 ---
with st.expander("📂 저장된 사양 관리", expanded=True):
    col_load1, col_load2, col_load3 = st.columns([0.6, 0.2, 0.2])
    with col_load1:
        st.selectbox("관리할 사양을 선택하세요", 
                     options=["선택하세요"] + list(st.session_state.saved_chamber_specs.keys()), 
                     key="spec_to_load")
    with col_load2:
        st.button("📥 선택한 사양 불러오기", on_click=load_chamber_spec_callback, use_container_width=True)
    with col_load3:
        if st.button("⚠️ 선택한 사양 삭제", use_container_width=True):
            spec_name_to_delete = st.session_state.spec_to_load
            if spec_name_to_delete != "선택하세요" and spec_name_to_delete in st.session_state.saved_chamber_specs:
                del st.session_state.saved_chamber_specs[spec_name_to_delete]
                st.session_state.spec_to_load = "선택하세요"
                st.success(f"'{spec_name_to_delete}' 사양을 삭제했습니다.")
                st.rerun()
            else:
                st.warning("삭제할 사양을 먼저 선택해주세요.")

st.markdown("---")
st.subheader("1. 챔버 사양")
c1, c2, c3 = st.columns(3)
c1.number_input("가로 (W, mm)", key='chamber_w', on_change=update_fan_recommendation)
c1.selectbox("단열재 종류", options=list(K_VALUES.keys()), key='insulation_type')
c2.number_input("세로 (D, mm)", key='chamber_d', on_change=update_fan_recommendation)
c2.number_input("단열재 두께 (mm)", min_value=1, step=1, key='insulation_thickness')
c3.number_input("높이 (H, mm)", key='chamber_h', on_change=update_fan_recommendation)
c3.number_input("내부 벽체 두께 (mm)", min_value=0.1, step=0.1, format="%.1f", key='sus_thickness')

st.subheader("2. 온도 조건")
c1, c2, c3 = st.columns(3)
c1.number_input("챔버 최저 온도 사양 (°C)", step=-1.0, format="%.1f", key='min_temp_spec')
c2.number_input("챔버 최고 온도 사양 (°C)", step=1.0, format="%.1f", key='max_temp_spec')
c3.number_input("외부 설정 온도 (°C)", step=1.0, format="%.1f", key='outside_temp')

st.number_input("목표 운전 온도 (°C)", 
                 min_value=st.session_state.min_temp_spec, 
                 max_value=st.session_state.max_temp_spec, 
                 step=1.0, format="%.1f", key='target_temp')

st.subheader("3. 내부 부하")
# (이하 UI 구성 코드는 제공된 버전과 동일하게 유지)
c1, c2 = st.columns(2)
c1.number_input("팬/모터 정격 부하 (kW)", key='fan_motor_load', format="%.2f", help="챔버 크기를 변경하면 자동 추천값이 업데이트됩니다.")
c2.slider("온도 유지 시 팬/모터 부하율 (%)", 0, 100, key='fan_soak_factor')
st.slider(
    "최소 구동 부하율 (%)", 0, 100,
    key='min_soak_load_factor',
    help="실제 장비가 작동 중 소비하는 최소한의 전력 비율입니다. Ramp와 Soak 모두에 적용됩니다."
)
st.selectbox("제품 부하 종류", options=['없음', '각형 배터리'], key='load_type')
if st.session_state.load_type == '각형 배터리':
    c1, c2 = st.columns(2)
    c1.number_input("챔버 내 셀 개수", min_value=1, step=1, key='num_cells')
    c2.selectbox("셀 사이즈 선택", options=['211Ah (현대차 규격)', '기타'], key='cell_size')

st.subheader("4. 온도 변화 속도")
st.number_input("사용자 목표 승온/강하 속도 (°C/min)", key='ramp_rate', step=0.1, format="%.1f", help="이 값은 필요 열/냉동 부하 및 승온/강하 시간을 계산하는 기준이 됩니다.")

st.subheader("5. 냉동 및 가열 방식")
c1, c2 = st.columns(2)
with c1:
    st.selectbox("설치된 냉동 방식", options=['1원 냉동', '2원 냉동'], key='refrigeration_system')
with c2:
    st.number_input("실제 히터 용량 (kW)", min_value=0.0, step=0.1, key='heater_capacity')
if st.session_state.refrigeration_system == '1원 냉동':
    c1, c2 = st.columns(2)
    c1.selectbox("실제 장비 마력 (HP)", options=[2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0], key='actual_hp_1stage')
    c2.number_input("실제 장비 정격 소비 전력 (kW)", min_value=0.0, step=0.1, key='actual_rated_power_1stage')
elif st.session_state.refrigeration_system == '2원 냉동':
    st.markdown("###### 2원 냉동 시스템 사양")
    c1, c2 = st.columns(2)
    c1.selectbox("1단(고온측) 마력 (HP)", options=[2.0, 3.0, 5.0, 7.5, 10.0], key='actual_hp_2stage_h')
    c2.number_input("1단(고온측) 정격 전력 (kW)", min_value=0.0, step=0.1, key='actual_rated_power_2stage_h')
    c3, c4 = st.columns(2)
    c3.selectbox("2단(저온측) 마력 (HP)", options=[2.0, 3.0, 5.0, 7.5, 10.0], key='actual_hp_2stage_l')
    c4.number_input("2단(저온측) 정격 전력 (kW)", min_value=0.0, step=0.1, key='actual_rated_power_2stage_l')

st.subheader("6. 냉각 방식")
c1, c2, c3 = st.columns(3)
c1.selectbox("냉각 방식", options=['공냉식', '수냉식'], key='cooling_type')
if st.session_state.cooling_type == '수냉식':
    c2.number_input("공급 냉각수 기준 온도 (°C)", min_value=0.1, step=0.1, format="%.1f", key='cooling_water_supply_temp', help="공급되는 냉각수(PCW)의 온도는 냉동기 효율에 영향을 줍니다.")
    c3.number_input("냉각수 설계 온도차 (ΔT, °C)", min_value=0.1, step=0.1, format="%.1f", key='cooling_water_delta_t')

st.markdown("---")

# --- 5. 자동 계산 로직 ---
st.subheader("자동 계산 결과")
st.slider("안전율 (Safety Factor)", 1.0, 3.0, key='safety_factor', help="계산된 총 열부하에 적용할 안전율입니다.")
specs = st.session_state
k_value = K_VALUES.get(specs.insulation_type, 0.023)
thickness_m = specs.insulation_thickness / 1000.0
U_value = (k_value / thickness_m) if thickness_m > 0 else 0
A = 2 * ((specs.chamber_w * specs.chamber_d) + (specs.chamber_w * specs.chamber_h) + (specs.chamber_d * specs.chamber_h)) / 1_000_000
delta_T_abs = abs(specs.target_temp - specs.outside_temp)
conduction_load_abs = U_value * A * delta_T_abs
sus_volume_m3 = A * (specs.sus_thickness / 1000.0)
calculated_internal_mass = sus_volume_m3 * DENSITY_SUS
volume_m3 = (specs.chamber_w * specs.chamber_d * specs.chamber_h) / 1_000_000_000
ramp_rate_c_per_sec = specs.ramp_rate / 60.0
ramp_load_energy_per_c = (volume_m3 * 1.225 * 1005) + (calculated_internal_mass * 500)
ramp_load_w = ramp_load_energy_per_c * ramp_rate_c_per_sec
internal_product_load_w = specs.num_cells * 50.0 if specs.load_type == '각형 배터리' else 0.0
fan_motor_load_w_ramp = specs.fan_motor_load * 1000
fan_motor_load_w_soak = fan_motor_load_w_ramp * (specs.fan_soak_factor / 100.0)
is_heating = specs.target_temp > specs.outside_temp

# (이하 계산 로직은 제공된 버전과 동일하게 유지)
if is_heating:
    operating_system = "히터 (가열 중)"
    internal_gains_ramp = fan_motor_load_w_ramp + internal_product_load_w
    theoretical_heater_power_ramp_w = max(0, conduction_load_abs + ramp_load_w - internal_gains_ramp)
    min_heater_power_ramp_kw = specs.heater_capacity * (specs.min_soak_load_factor / 100.0)
    final_heater_power_ramp_w = max(theoretical_heater_power_ramp_w, min_heater_power_ramp_kw * 1000)
    target_ramp_time_h = (delta_T_abs / specs.ramp_rate) / 60.0 if specs.ramp_rate > 0 else float('inf')
    total_consumption_ramp_kw = (final_heater_power_ramp_w / 1000) + specs.fan_motor_load
    energy_ramp_kwh = total_consumption_ramp_kw * target_ramp_time_h if target_ramp_time_h != float('inf') else float('inf')
    internal_gains_soak = fan_motor_load_w_soak + internal_product_load_w
    theoretical_heater_power_soak_w = max(0, conduction_load_abs - internal_gains_soak)
    min_heater_power_soak_kw = specs.heater_capacity * (specs.min_soak_load_factor / 100.0)
    final_heater_power_soak_w = max(theoretical_heater_power_soak_w, min_heater_power_soak_kw * 1000)
    total_consumption_soak_kw = (final_heater_power_soak_w / 1000) + (specs.fan_motor_load * (specs.fan_soak_factor / 100.0))
    required_heater_power_ramp_w = theoretical_heater_power_ramp_w
    required_heater_power_soak_w = theoretical_heater_power_soak_w
    load_factor_ramp = 0.0; load_factor_soak = 0.0
    total_heat_load_ramp = 0.0; total_heat_load_soak = 0.0
    required_hp_ramp = 0.0; required_hp_soak = 0.0
else:
    if specs.target_temp > -25:
        operating_system = "1원 냉동 (냉각 중)"; sorted_cop_items = sorted(COP_TABLE_1STAGE.items())
    else:
        operating_system = "2원 냉동 (냉각 중)"; sorted_cop_items = sorted(COP_TABLE_2STAGE.items())
    total_heat_load_ramp = conduction_load_abs + ramp_load_w + internal_product_load_w + fan_motor_load_w_ramp
    total_heat_load_soak = conduction_load_abs + internal_product_load_w + fan_motor_load_w_soak
    cop = np.interp(specs.target_temp, [k for k,v in sorted_cop_items], [v for k,v in sorted_cop_items])
    required_electrical_power_ramp = total_heat_load_ramp / cop if cop > 0 else float('inf')
    required_hp_ramp = (required_electrical_power_ramp * specs.safety_factor) / 746
    required_electrical_power_soak = total_heat_load_soak / cop if cop > 0 else float('inf')
    required_hp_soak = (required_electrical_power_soak * specs.safety_factor) / 746
    actual_hp, actual_rated_power = 0, 0
    if specs.refrigeration_system == '1원 냉동':
        actual_hp = specs.actual_hp_1stage; actual_rated_power = specs.actual_rated_power_1stage
    elif specs.refrigeration_system == '2원 냉동':
        if operating_system.startswith("1원"):
            actual_hp = specs.actual_hp_2stage_h; actual_rated_power = specs.actual_rated_power_2stage_h
        else:
            actual_hp = specs.actual_hp_2stage_h + specs.actual_hp_2stage_l; actual_rated_power = specs.actual_rated_power_2stage_h + specs.actual_rated_power_2stage_l
    min_load_power_ramp_kw = actual_rated_power * (specs.min_soak_load_factor / 100.0)
    theoretical_power_ramp_kw = actual_rated_power * (required_hp_ramp / actual_hp) if actual_hp > 0 else 0
    final_estimated_power_ramp_kw = max(min_load_power_ramp_kw, theoretical_power_ramp_kw)
    load_factor_ramp = final_estimated_power_ramp_kw / actual_rated_power if actual_rated_power > 0 else 0
    min_load_power_soak_kw = actual_rated_power * (specs.min_soak_load_factor / 100.0)
    theoretical_power_soak_kw = actual_rated_power * (required_hp_soak / actual_hp) if actual_hp > 0 else 0
    final_estimated_power_soak_kw = max(min_load_power_soak_kw, theoretical_power_soak_kw)
    load_factor_soak = final_estimated_power_soak_kw / actual_rated_power if actual_rated_power > 0 else 0
    total_consumption_ramp_kw = final_estimated_power_ramp_kw + specs.fan_motor_load
    total_consumption_soak_kw = final_estimated_power_soak_kw + (specs.fan_motor_load * (specs.fan_soak_factor / 100.0))
    required_heater_power_ramp_w = 0.0; required_heater_power_soak_w = 0.0

# --- 6. 결과 표시 ---
st.markdown("---")
st.subheader("✔️ 최종 소비 전력 예측")
# (이하 결과 표시 코드는 제공된 버전과 동일하게 유지)
st.info(f"현재 작동 방식: **{operating_system}** (목표 온도 {specs.target_temp}°C, 외부 온도 {specs.outside_temp}°C 기준)")
c1, c2 = st.columns(2)
with c1:
    st.markdown("##### 🌡️ 온도 변화 시")
    if is_heating:
        st.metric("평균 필요 히터 출력", f"{required_heater_power_ramp_w / 1000:.2f} kW", help="목표 승온 속도를 유지하기 위해 필요한 평균 히터 출력입니다.")
        st.metric("목표 승온 시간", f"{target_ramp_time_h:.2f} H", help="사용자가 설정한 승온 속도로 계산된 시간입니다.")
        st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_ramp_kw:.2f} kW", help="승온 중 히터와 팬이 소비하는 평균 전력입니다.")
        st.metric("예상 소비 전력량", f"{energy_ramp_kwh:.2f} kWh", help="목표 승온 시간 동안 소비되는 총 에너지입니다.")
        if (required_heater_power_ramp_w / 1000) > specs.heater_capacity:
            st.warning(f"경고: 필요 히터 출력이 실제 히터 용량({specs.heater_capacity}kW)보다 큽니다. 목표 승온 속도를 달성할 수 없습니다.")
    else:
        st.metric("총 열부하", f"{total_heat_load_ramp:.2f} W")
        st.metric("최소 필요 마력 (HP)", f"{required_hp_ramp:.2f} HP")
        st.metric("예상 부하율", f"{load_factor_ramp:.1%}")
        st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_ramp_kw:.2f} kW")
with c2:
    st.markdown("##### 💧 온도 유지 시")
    if is_heating:
        st.metric("필요 히터 출력", f"{required_heater_power_soak_w / 1000:.2f} kW")
        st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_soak_kw:.2f} kW")
    else:
        st.metric("총 열부하", f"{total_heat_load_soak:.2f} W")
        st.metric("최소 필요 마력 (HP)", f"{required_hp_soak:.2f} HP")
        st.metric("예상 부하율", f"{load_factor_soak:.1%}")
        st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_soak_kw:.2f} kW")

if not is_heating and load_factor_ramp > 1.0:
    st.warning("경고: '온도 변화 시' 필요 마력이 실제 장비의 마력보다 큽니다. 장비 용량이 부족할 수 있습니다.")

st.markdown("---")
st.subheader("❄️ 냉각 시스템 요구 사양")
# (이하 냉각 시스템 요구 사양 코드는 제공된 버전과 동일하게 유지)
total_heat_to_reject_ramp = total_heat_load_ramp + (total_consumption_ramp_kw * 1000) if not is_heating else 0
total_heat_to_reject_soak = total_heat_load_soak + (total_consumption_soak_kw * 1000) if not is_heating else 0
correction_temps = sorted(COOLING_TEMP_CORRECTION_FACTORS.keys())
correction_factors = [COOLING_TEMP_CORRECTION_FACTORS[t] for t in correction_temps]
water_temp_correction_factor = np.interp(specs.cooling_water_supply_temp, correction_temps, correction_factors)
adjusted_heat_reject_ramp = total_heat_to_reject_ramp * water_temp_correction_factor
adjusted_heat_reject_soak = total_heat_to_reject_soak * water_temp_correction_factor

c1, c2 = st.columns(2)
with c1:
    st.markdown("##### 🌡️ 온도 변화 시")
    if specs.cooling_type == '공냉식':
        st.metric("총 발열량", f"{total_heat_to_reject_ramp / 1000:.2f} kW", help=f"({(total_heat_to_reject_ramp * WATT_TO_KCAL_H):,.0f} kcal/h)")
    elif specs.cooling_type == '수냉식':
        required_flow_rate = (adjusted_heat_reject_ramp / (4186 * specs.cooling_water_delta_t)) * 60 if specs.cooling_water_delta_t > 0 else 0
        st.metric("필요 냉각수 유량", f"{required_flow_rate:.2f} LPM", 
                  help=f"냉각수 온도({specs.cooling_water_supply_temp}°C) 보정계수({water_temp_correction_factor:.2f}) 적용됨")
with c2:
    st.markdown("##### 💧 온도 유지 시")
    if specs.cooling_type == '공냉식':
        st.metric("총 발열량", f"{total_heat_to_reject_soak / 1000:.2f} kW", help=f"({(total_heat_to_reject_soak * WATT_TO_KCAL_H):,.0f} kcal/h)")
    elif specs.cooling_type == '수냉식':
        required_flow_rate = (adjusted_heat_reject_soak / (4186 * specs.cooling_water_delta_t)) * 60 if specs.cooling_water_delta_t > 0 else 0
        st.metric("필요 냉각수 유량", f"{required_flow_rate:.2f} LPM",
                  help=f"냉각수 온도({specs.cooling_water_supply_temp}°C) 보정계수({water_temp_correction_factor:.2f}) 적용됨")

# --- 7. 설정값 저장 ---
st.markdown("---")
with st.form("chamber_save_form"):
    chamber_spec_name = st.text_input("저장할 사양 이름")
    submitted = st.form_submit_button("💾 현재 상세 사양 저장")
    if submitted:
        if not chamber_spec_name:
            st.warning("사양 이름을 입력해주세요.")
        else:
            # ★★★★★ 수정된 부분: 모든 UI 입력값을 저장하여 칠러 페이지 연동 오류 해결 ★★★★★
            data_to_save = {key: st.session_state[key] for key in CHAMBER_DEFAULTS}
            
            # 계산된 결과값 추가
            data_to_save['total_consumption_ramp_kw'] = total_consumption_ramp_kw
            data_to_save['total_consumption_soak_kw'] = total_consumption_soak_kw
            
            # (이하 칠러 연동을 위한 최대 발열량 계산 로직은 제공된 버전과 동일하게 유지)
            temp_target_for_chiller = specs.min_temp_spec
            temp_delta_for_chiller = abs(temp_target_for_chiller - specs.outside_temp)
            conduction_load_chiller = U_value * A * temp_delta_for_chiller
            total_heat_load_ramp_chiller = conduction_load_chiller + ramp_load_w + internal_product_load_w + fan_motor_load_w_ramp
            
            if temp_target_for_chiller > -25:
                sorted_cop_items_chiller = sorted(COP_TABLE_1STAGE.items())
            else:
                sorted_cop_items_chiller = sorted(COP_TABLE_2STAGE.items())
            cop_chiller = np.interp(temp_target_for_chiller, [k for k,v in sorted_cop_items_chiller], [v for k,v in sorted_cop_items_chiller])
            required_elec_power_chiller = total_heat_load_ramp_chiller / cop_chiller if cop_chiller > 0 else float('inf')
            required_hp_chiller = (required_elec_power_chiller * specs.safety_factor) / 746
            
            actual_hp_chiller, actual_rated_power_chiller = 0, 0
            if specs.refrigeration_system == '1원 냉동':
                actual_hp_chiller, actual_rated_power_chiller = specs.actual_hp_1stage, specs.actual_rated_power_1stage
            else:
                actual_hp_chiller = specs.actual_hp_2stage_h + specs.actual_hp_2stage_l
                actual_rated_power_chiller = specs.actual_rated_power_2stage_h + specs.actual_rated_power_2stage_l

            min_load_power_chiller = actual_rated_power_chiller * (specs.min_soak_load_factor / 100.0)
            theoretical_power_chiller = actual_rated_power_chiller * (required_hp_chiller / actual_hp_chiller) if actual_hp_chiller > 0 else 0
            final_power_chiller = max(min_load_power_chiller, theoretical_power_chiller)
            total_consumption_chiller = final_power_chiller + specs.fan_motor_load
            max_heat_rejection_w = total_heat_load_ramp_chiller + (total_consumption_chiller * 1000)
            
            data_to_save['max_heat_rejection_w'] = max_heat_rejection_w
            
            st.session_state.saved_chamber_specs[chamber_spec_name] = data_to_save
            st.success(f"'{chamber_spec_name}' 사양이 저장되었습니다 ✅")


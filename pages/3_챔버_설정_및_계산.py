import streamlit as st
import math
import numpy as np

st.set_page_config(layout="wide")
st.title("🔌 챔버 설정 및 계산")
st.info("이 페이지에서 입력한 값은 '레시피 계산기'의 전체 전력량 계산에 반영됩니다.")

# --- 콜백 함수 정의 ---
def update_fan_recommendation():
    """챔버 크기가 변경될 때만 호출되어 팬/모터 부하 추천값을 업데이트하는 함수"""
    volume_m3 = (st.session_state.chamber_w * st.session_state.chamber_d * st.session_state.chamber_h) / 1_000_000_000
    
    if volume_m3 < 1:
        default_fan_load = 0.5
    elif 1 <= volume_m3 < 8:
        default_fan_load = 1.5
    else:
        default_fan_load = 2.5
    
    st.session_state.fan_motor_load = default_fan_load

# --- st.session_state 초기화 ---
def initialize_chamber_specs():
    defaults = {
        'chamber_w': 1000, 'chamber_d': 1000, 'chamber_h': 1000,
        'insulation_type': '우레탄폼', 'insulation_thickness': 100,
        'sus_thickness': 1.2, # 내부 벽체 두께 기본값 추가
        'min_temp_spec': -10.0, 'max_temp_spec': 80.0,
        'outside_temp': 25.0, 'load_type': '없음', 'num_cells': 4,
        'cell_size': '211Ah (현대차 규격)', 'ramp_rate': 1.0,
        'actual_hp': 5.0, # 실제 장비 마력 기본값
        'actual_rated_power': 3.5 # 실제 장비 정격 전력 기본값 (kW)
        # 'fan_motor_load'와 'internal_mass' 삭제
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_chamber_specs()

# --- 단열재별 '열전도율(k)' 데이터 ---
K_VALUES = {"우레탄폼": 0.023, "글라스울": 0.040, "세라크울": 0.150}
DENSITY_SUS = 7930  # SUS 비중 (kg/m³)

# --- 1. 챔버 사양 입력 UI ---
st.subheader("1. 챔버 사양 입력")
col1, col2, col3 = st.columns(3)
with col1:
    st.number_input("가로 (W, mm)", key='chamber_w', on_change=update_fan_recommendation)
    st.selectbox("단열재 종류", options=list(K_VALUES.keys()), key='insulation_type')
with col2:
    st.number_input("세로 (D, mm)", key='chamber_d', on_change=update_fan_recommendation)
    st.number_input("단열재 두께 (mm)", min_value=1, step=1, key='insulation_thickness')
with col3:
    st.number_input("높이 (H, mm)", key='chamber_h', on_change=update_fan_recommendation)
    # ★★★★★ 내부 벽체 두께 입력창 추가 ★★★★★
    st.number_input("내부 벽체 두께 (mm)", min_value=0.1, step=0.1, format="%.1f", key='sus_thickness')
st.markdown("---")

# --- 2. 온도 조건 입력 UI ---
st.subheader("2. 온도 조건 입력")
col_temp1, col_temp2, col_temp3 = st.columns(3)
with col_temp1:
    st.number_input("챔버 최저 온도 사양 (°C)", step=1.0, format="%.1f", key='min_temp_spec')
with col_temp2:
    st.number_input("챔버 최고 온도 사양 (°C)", step=1.0, format="%.1f", key='max_temp_spec')
with col_temp3:
    st.number_input("외부 설정 온도 (°C)", step=1.0, format="%.1f", key='outside_temp', help="챔버가 놓인 공간의 평균 온도를 입력합니다.")

st.markdown("---")

# --- 3. 내부 부하 설정 ---
st.subheader("3. 내부 부하 설정")

# 팬/모터 '정격' 부하 입력
st.number_input("팬/모터 정격 부하 (kW)", key='fan_motor_load', help="온도 변화 시 사용되는 최대 부하입니다.", format="%.2f")

# ★★★★★ 온도 유지 시 부하율 슬라이더 추가 ★★★★★
st.slider(
    "온도 유지 시 팬/모터 부하율 (%)", 
    min_value=0, max_value=100, value=30, # 기본값 30%
    key='fan_soak_factor',
    help="온도 유지 상태일 때 팬/모터가 정격 부하의 몇 %로 작동할지 설정합니다."
)

if st.session_state.load_type == '각형 배터리':
    col_batt1, col_batt2 = st.columns(2)
    with col_batt1:
        st.number_input("챔버 내 셀 개수", min_value=1, step=1, key='num_cells')
    with col_batt2:
        st.selectbox("셀 사이즈 선택 (일반)", options=['211Ah (현대차 규격)', '기타'], key='cell_size')

st.markdown("---")

# --- 4. 온도 변화 속도 설정 ---
st.subheader("4. 온도 변화 속도 설정")
st.number_input("목표 온도 변화 속도 (°C/min)", key='ramp_rate', step=0.1, format="%.1f")

st.markdown("---")

# ★★★★★ 5. 실제 냉동기 사양 입력 UI 추가 ★★★★★
st.subheader("5. 실제 냉동기 사양 입력")

col_ac1, col_ac2 = st.columns(2)
with col_ac1:
    st.selectbox("실제 장비 마력 (HP)", options=[2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0], key='actual_hp')
with col_ac2:
    st.number_input("실제 장비 정격 소비 전력 (kW)", min_value=0.0, step=0.1, format="%.2f", key='actual_rated_power')

# --- 5. 자동 계산 결과 ---
st.subheader("자동 계산 결과")

COP_TABLE = {
    10: 4.0, 0: 3.0, -10: 2.2, -20: 1.5, -30: 0.9, -40: 0.5, -50: 0.3
}

sorted_cop_items = sorted(COP_TABLE.items())
cop_temps = np.array([item[0] for item in sorted_cop_items])
cop_values = np.array([item[1] for item in sorted_cop_items])

# --- st.session_state에서 모든 최신 값 가져오기 ---
chamber_w = st.session_state.chamber_w
chamber_d = st.session_state.chamber_d
chamber_h = st.session_state.chamber_h
insulation_type = st.session_state.insulation_type
insulation_thickness = st.session_state.insulation_thickness
target_temp = st.session_state.min_temp_spec
outside_temp = st.session_state.outside_temp
load_type = st.session_state.load_type
num_cells = st.session_state.num_cells
fan_motor_load_w = st.session_state.fan_motor_load * 1000
ramp_rate = st.session_state.ramp_rate
sus_thickness_m = st.session_state.sus_thickness / 1000.0 # 내부 벽체 두께

# 1. 전도 부하 계산
k_value = K_VALUES.get(insulation_type, 0.023)
thickness_m = insulation_thickness / 1000.0
thermal_resistance_R = thickness_m / k_value if k_value > 0 else float('inf')
U_value = 1 / thermal_resistance_R if thermal_resistance_R > 0 else 0
A = 2 * ((chamber_w * chamber_d) + (chamber_w * chamber_h) + (chamber_d * chamber_h)) / 1_000_000
delta_T = abs(target_temp - outside_temp)
conduction_load_w = U_value * A * delta_T

# 2. 내부 구조물 무게(SUS) 자동 계산
sus_volume_m3 = A * sus_thickness_m
calculated_internal_mass = sus_volume_m3 * DENSITY_SUS

# 3. 온도 변화 부하(Ramp Load) 계산
volume_m3 = (chamber_w * chamber_d * chamber_h) / 1_000_000_000
ramp_rate_c_per_sec = ramp_rate / 60.0
air_mass_kg = volume_m3 * 1.225
air_load_w = air_mass_kg * 1005 * ramp_rate_c_per_sec
specific_heat_sus = 500
internal_mass_load_w = calculated_internal_mass * specific_heat_sus * ramp_rate_c_per_sec
ramp_load_w = air_load_w + internal_mass_load_w

# 4. 내부 제품 부하 계산
internal_product_load_w = 0.0
if load_type == '각형 배터리':
    heat_per_cell_w = 50.0
    internal_product_load_w = num_cells * heat_per_cell_w

# ★★★★★ 두 가지 시나리오의 총 열부하 계산 ★★★★★
# 시나리오 1: 온도 변화 시 (모든 부하 합산)
total_heat_load_ramp = conduction_load_w + ramp_load_w + internal_product_load_w + fan_motor_load_w
# 시나리오 2: 온도 유지 시 (온도 변화 부하 제외)
total_heat_load_soak = conduction_load_w + internal_product_load_w + fan_motor_load_w

# --- 각 시나리오별 최종 전력 예측 ---
# COP 계산 (두 시나리오 공통)
cop = np.interp(target_temp, cop_temps, cop_values)

# 시나리오 1: 온도 변화 시 최종 계산
required_electrical_power_ramp = total_heat_load_ramp / cop if cop > 0 else float('inf')
required_hp_ramp = (required_electrical_power_ramp * 1.3) / 746
load_factor_ramp = required_hp_ramp / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_ramp = st.session_state.actual_rated_power * load_factor_ramp

# 시나리오 2: 온도 유지 시 최종 계산
required_electrical_power_soak = total_heat_load_soak / cop if cop > 0 else float('inf')
required_hp_soak = (required_electrical_power_soak * 1.3) / 746
load_factor_soak = required_hp_soak / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_soak = st.session_state.actual_rated_power * load_factor_soak

# 결과 표시
st.markdown("---")
st.subheader("✔️ 최종 소비 전력 예측")

# 각 시나리오별 부하율 및 소비 전력 계산
load_factor_ramp = required_hp_ramp / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_ramp = st.session_state.actual_rated_power * load_factor_ramp

load_factor_soak = required_hp_soak / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_soak = st.session_state.actual_rated_power * load_factor_soak

# 결과 표시
col1, col2 = st.columns(2)
fan_motor_load_kw = st.session_state.fan_motor_load
fan_soak_factor = st.session_state.fan_soak_factor / 100.0 # %를 소수점으로 변환

with col1:
    st.markdown("##### 🌡️ 온도 변화 시")
    st.metric("총 열부하", f"{total_heat_load_ramp:.2f} W")
    st.metric("최소 필요 마력 (HP)", f"{required_hp_ramp:.2f} HP")
    st.metric("예상 부하율", f"{load_factor_ramp:.1%}")
    # 온도 변화 시에는 정격 부하 100%를 그대로 더함
    total_consumption_ramp = estimated_power_ramp + fan_motor_load_kw
    st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_ramp:.2f} kW")

with col2:
    st.markdown("##### 💧 온도 유지 시")
    st.metric("총 열부하", f"{total_heat_load_soak:.2f} W")
    st.metric("최소 필요 마력 (HP)", f"{required_hp_soak:.2f} HP")
    st.metric("예상 부하율", f"{load_factor_soak:.1%}")
    # ★★★★★ 온도 유지 시에는 부하율을 적용하여 계산 ★★★★★
    fan_soak_load_kw = fan_motor_load_kw * fan_soak_factor
    total_consumption_soak = estimated_power_soak + fan_soak_load_kw
    st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_soak:.2f} kW")

# 부하율이 100%를 초과할 경우 경고 메시지 표시
if load_factor_ramp > 1.0:
    st.warning("경고: '온도 변화 시' 필요 마력이 실제 장비의 마력보다 큽니다. 장비 용량이 부족할 수 있습니다.")

st.info("💡 위 계산은 설정된 모든 부하와 온도별 성능 계수(COP)를 반영한 결과입니다.")
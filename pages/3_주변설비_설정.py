import streamlit as st
import math
import numpy as np

st.set_page_config(layout="wide")
st.title("🔌 주변설비 설정 및 계산")
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
# ★★★★★ '내부 구조물 무게' 수동 입력창 삭제 ★★★★★
st.number_input("팬/모터 부하 (kW)", key='fan_motor_load', help="챔버 크기를 변경하면 자동으로 추천값이 업데이트됩니다.", format="%.2f")

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

# 5. 총 열부하 계산
total_heat_load_w = conduction_load_w + ramp_load_w + internal_product_load_w + fan_motor_load_w

# ★★★★★ 6. 최소 필요 마력(HP) 계산 (로직 수정) ★★★★★
# (1) 현재 목표 온도에 맞는 COP 값을 테이블에서 보간법으로 추정
#     np.interp(목표값, x축 데이터, y축 데이터)
cop = np.interp(target_temp, cop_temps, cop_values)

# (2) COP를 이용해 실제 필요한 '전기 에너지' 계산
#     필요 전기(W) = 제거할 열(W) / COP
required_electrical_power_w = total_heat_load_w / cop if cop > 0 else float('inf')

# (3) 필요한 전기 에너지를 마력(HP)으로 변환 (1 HP ≈ 746 W)
#     여기에 안전율 1.3을 적용
required_hp = (required_electrical_power_w * 1.3) / 746

# ★★★★★ 부하율 및 실제 소비 전력 계산 추가 ★★★★★
actual_hp = st.session_state.actual_hp
actual_rated_power = st.session_state.actual_rated_power

# (1) 부하율 계산
load_factor = required_hp / actual_hp if actual_hp > 0 else 0

# (2) 예상 실제 소비 전력 계산
estimated_actual_power_kw = actual_rated_power * load_factor

# --- 결과 표시 ---
col_res1, col_res2, col_res3 = st.columns(3)
with col_res1:
    st.metric("총 열부하 (Total Heat Load)", f"{total_heat_load_w:.2f} W")
with col_res2:
    st.metric("예상 성능 계수 (COP)", f"{cop:.2f}")
with col_res3:
    st.metric("최소 필요 마력 (HP)", f"{required_hp:.2f} HP")

st.markdown("---")
st.subheader("✔️ 최종 소비 전력 예측")

# 새로운 결과 표시
col_final1, col_final2 = st.columns(2)
with col_final1:
    st.metric("예상 부하율", f"{load_factor:.1%}") # % 형태로 표시
with col_final2:
    st.metric("예상 실제 소비 전력", f"{estimated_actual_power_kw:.2f} kW")

# 부하율이 100%를 초과할 경우 경고 메시지 표시
if load_factor > 1.0:
    st.warning("경고: 계산된 필요 마력이 실제 장비의 마력보다 큽니다. 장비 용량이 부족할 수 있습니다.")

st.info("💡 위 계산은 설정된 모든 부하와 온도별 성능 계수(COP)를 반영한 결과입니다.")
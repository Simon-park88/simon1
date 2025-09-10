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
        'actual_rated_power': 3.5, # 실제 장비 정격 전력 기본값 (kW)
        'cooling_type': '공냉식', # 냉각 방식 기본값
        'cooling_water_delta_t': 5.0 # 냉각수 온도차 기본값
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
    st.number_input(
        "챔버 최저 온도 사양 (°C)", 
        step=1.0, 
        format="%.1f", 
        key='min_temp_spec'
    )

with col_temp2:
    st.number_input(
        "목표 운전 온도 (°C)", 
        # ★★★★★ 이 부분이 추가되었습니다 ★★★★★
        min_value=st.session_state.min_temp_spec, # 최저 입력값을 '최저 온도 사양' 값으로 제한
        max_value=st.session_state.max_temp_spec, # 최고 입력값도 '최고 온도 사양'으로 제한
        # ★★★★★ 여기까지 추가 ★★★★★
        step=1.0, 
        format="%.1f", 
        key='target_temp',
        help="시뮬레이션하고 싶은 실제 운전 온도를 입력합니다."
    )

with col_temp3:
    st.number_input(
        "외부 설정 온도 (°C)", 
        step=1.0, 
        format="%.1f", 
        key='outside_temp'
    )

st.markdown("---")

# --- 3. 내부 부하 설정 ---
st.subheader("3. 내부 부하 설정")

# 팬/모터 '정격' 부하 입력
st.number_input("팬/모터 정격 부하 (kW)", key='fan_motor_load', value=1.5, help="온도 변화 시 사용되는 최대 부하입니다.", format="%.2f")

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

# ★★★★★ 5. 냉동 방식 및 실제 사양 입력 (UI 수정) ★★★★★
st.subheader("5. 냉동 방식 및 실제 사양 입력")

# 냉동 방식 수동 선택
refrigeration_system = st.selectbox(
    "설치된 냉동 방식 선택",
    options=['1원 냉동', '2원 냉동'],
    key='refrigeration_system',
    help="챔버에 설치된 실제 냉동 방식을 선택합니다."
)

# 선택된 냉동 방식에 따라 다른 입력창 표시
if st.session_state.refrigeration_system == '1원 냉동':
    col_ac1, col_ac2 = st.columns(2)
    with col_ac1:
        st.selectbox("실제 장비 마력 (HP)", options=[2.0, 3.0, 5.0, 7.5, 10.0], key='actual_hp_1stage')
    with col_ac2:
        st.number_input("실제 장비 정격 소비 전력 (kW)", min_value=0.0, value=3.0, step=0.1, key='actual_rated_power_1stage')

elif st.session_state.refrigeration_system == '2원 냉동':
    st.markdown("###### 2원 냉동 시스템 사양")
    col_2ac1, col_2ac2 = st.columns(2)
    with col_2ac1:
        st.selectbox("1단(고온측) 마력 (HP)", options=[2.0, 3.0, 5.0, 7.5, 10.0], key='actual_hp_2stage_h')
        st.selectbox("2단(저온측) 마력 (HP)", options=[2.0, 3.0, 5.0, 7.5, 10.0], key='actual_hp_2stage_l')
    with col_2ac2:
        st.number_input("1단(고온측) 정격 전력 (kW)", min_value=0.0, value=3.0, step=0.1, key='actual_rated_power_2stage_h')
        st.number_input("2단(저온측) 정격 전력 (kW)", min_value=0.0, value=3.0, step=0.1, key='actual_rated_power_2stage_l')

# ★★★★★ 6. 냉각 방식 설정 UI 추가 ★★★★★
st.markdown("---")
st.subheader("6. 냉각 방식 설정")

col_cool1, col_cool2 = st.columns(2)
with col_cool1:
    st.selectbox("냉각 방식", options=['공냉식', '수냉식'], key='cooling_type')

# 수냉식을 선택했을 때만 온도차 입력창 표시
if st.session_state.cooling_type == '수냉식':
    with col_cool2:
        st.number_input(
            "냉각수 설계 온도차 (ΔT, °C)", 
            min_value=0.1,
            value=5.0, 
            step=0.1, 
            format="%.1f", 
            key='cooling_water_delta_t',
            help="냉각수가 냉동기를 통과하며 상승하는 온도차입니다. (일반적으로 5°C)"
        )

# --- 5. 자동 계산 결과 ---
st.subheader("자동 계산 결과")

# ★★★★★ 안전율 설정 슬라이더 추가 ★★★★★
safety_factor = st.slider(
    "안전율 (Safety Factor)", 
    min_value=1.0, 
    max_value=3.0, 
    value=1.5, # 기본값 1.5배
    step=0.1,
    help="계산된 총 열부하에 적용할 안전율입니다. 제조업체는 보통 1.5~2.5배 이상의 높은 안전율을 적용합니다."
)

# 1원 냉동 사이클 COP 테이블
COP_TABLE_1STAGE = {
    10: 4.0, 0: 3.0, -10: 2.2, -20: 1.5, -25: 1.2 # -25°C 이하로는 효율 급감
}
# 2원 냉동 사이클 COP 테이블 (더 낮은 온도에서 더 높은 효율)
COP_TABLE_2STAGE = {
    -20: 2.5, -30: 2.0, -40: 1.5, -50: 1.1, -60: 0.8, -70: 0.5
}

# --- st.session_state에서 모든 최신 값 가져오기 ---
chamber_w = st.session_state.chamber_w
chamber_d = st.session_state.chamber_d
chamber_h = st.session_state.chamber_h
insulation_type = st.session_state.insulation_type
insulation_thickness = st.session_state.insulation_thickness
outside_temp = st.session_state.outside_temp
load_type = st.session_state.load_type
num_cells = st.session_state.num_cells
fan_motor_load_w = st.session_state.fan_motor_load * 1000
ramp_rate = st.session_state.ramp_rate
sus_thickness_m = st.session_state.sus_thickness / 1000.0 # 내부 벽체 두께
outside_temp = st.session_state.outside_temp
# 2. 온도차(ΔT) 계산
min_temp_spec = st.session_state.min_temp_spec
target_temp = st.session_state.target_temp
delta_T = abs(target_temp - outside_temp)

# ★★★★★ 최종 소비 전력 예측 (로직 수정) ★★★★★
# '목표 운전 온도'에 따라 실제 작동할 COP 테이블 선택
if st.session_state.target_temp > -25:
    operating_system = "1원 냉동 (작동 중)"
    sorted_cop_items = sorted(COP_TABLE_1STAGE.items())
else: # -25°C 이하 운전
    operating_system = "2원 냉동 (작동 중)"
    sorted_cop_items = sorted(COP_TABLE_2STAGE.items())

cop_temps = np.array([item[0] for item in sorted_cop_items])
cop_values = np.array([item[1] for item in sorted_cop_items])
cop = np.interp(st.session_state.target_temp, cop_temps, cop_values)

# 설치된 시스템과 운전 조건에 따라 실제 마력과 정격 전력을 결정
actual_hp, actual_rated_power = 0, 0
if st.session_state.refrigeration_system == '1원 냉동':
    actual_hp = st.session_state.actual_hp_1stage
    actual_rated_power = st.session_state.actual_rated_power_1stage
elif st.session_state.refrigeration_system == '2원 냉동':
    if operating_system == "1원 냉동 (작동 중)": # -25°C 이상 운전
        actual_hp = st.session_state.actual_hp_2stage_h
        actual_rated_power = st.session_state.actual_rated_power_2stage_h
    else: # -25°C 이하 운전 (두 시스템 모두 작동)
        actual_hp = st.session_state.actual_hp_2stage_h + st.session_state.actual_hp_2stage_l
        actual_rated_power = st.session_state.actual_rated_power_2stage_h + st.session_state.actual_rated_power_2stage_l

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
required_hp_ramp = (required_electrical_power_ramp * safety_factor) / 746
load_factor_ramp = required_hp_ramp / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_ramp = st.session_state.actual_rated_power * load_factor_ramp

# 시나리오 2: 온도 유지 시 최종 계산
required_electrical_power_soak = total_heat_load_soak / cop if cop > 0 else float('inf')
required_hp_soak = (required_electrical_power_soak * safety_factor) / 746
load_factor_soak = required_hp_soak / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_soak = st.session_state.actual_rated_power * load_factor_soak

# ★★★★★ 냉각 부하 계산 추가 ★★★★★
# 버려야 할 총 열량(W) = 챔버 총 열부하(W) + 냉동기 소비 전력(W)
# 두 시나리오에 대해 각각 계산
total_heat_to_reject_ramp = total_heat_load_ramp + (estimated_power_ramp * 1000)
total_heat_to_reject_soak = total_heat_load_soak + (estimated_power_soak * 1000)

# 결과 표시
st.markdown("---")
st.subheader("✔️ 최종 소비 전력 예측")

# 각 시나리오별 부하율 및 소비 전력 계산
load_factor_ramp = required_hp_ramp / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_ramp = st.session_state.actual_rated_power * load_factor_ramp

load_factor_soak = required_hp_soak / st.session_state.actual_hp if st.session_state.actual_hp > 0 else 0
estimated_power_soak = st.session_state.actual_rated_power * load_factor_soak

# 결과 표시
st.markdown("---")
# 선택된 냉동 방식을 명확하게 표시
st.info(f"선택된 시스템: **{st.session_state.refrigeration_system}** | 현재 작동 방식: **{operating_system}** (목표 온도 기준)")

col1, col2 = st.columns(2)
with col1:
    st.markdown("##### 🌡️ 온도 변화 시")
    st.metric("총 열부하", f"{total_heat_load_ramp:.2f} W")
    st.metric("최소 필요 마력 (HP)", f"{required_hp_ramp:.2f} HP")
    st.metric("예상 부하율", f"{load_factor_ramp:.1%}")
    st.metric("챔버 전체 예상 소비 전력", f"{(estimated_power_ramp + st.session_state.fan_motor_load):.2f} kW")

with col2:
    st.markdown("##### 💧 온도 유지 시")
    st.metric("총 열부하", f"{total_heat_load_soak:.2f} W")
    st.metric("최소 필요 마력 (HP)", f"{required_hp_soak:.2f} HP")
    st.metric("예상 부하율", f"{load_factor_soak:.1%}")
    st.metric("챔버 전체 예상 소비 전력", f"{(estimated_power_soak + st.session_state.fan_motor_load):.2f} kW")
    
# 부하율이 100%를 초과할 경우 경고 메시지 표시
if load_factor_ramp > 1.0:
    st.warning("경고: '온도 변화 시' 필요 마력이 실제 장비의 마력보다 큽니다. 장비 용량이 부족할 수 있습니다.")

st.markdown("---")
st.subheader("❄️ 냉각 시스템 요구 사양")

cooling_type = st.session_state.cooling_type

# --- 시나리오별 냉각 요구 사양 표시 ---
col_cool_res1, col_cool_res2 = st.columns(2)

with col_cool_res1:
    st.markdown("##### 🌡️ 온도 변화 시")
    if cooling_type == '공냉식':
        # 총 발열량을 BTU/h 단위로도 변환하여 표시 (1 W ≈ 3.41 BTU/h)
        st.metric("총 발열량", f"{total_heat_to_reject_ramp / 1000:.2f} kW", help=f"({(total_heat_to_reject_ramp * 3.41):,.0f} BTU/h)")
        st.info("해당 발열량을 처리할 수 있는 용량의 공조 시스템이 필요합니다.")
    elif cooling_type == '수냉식':
        # 필요 유량 계산 (LPM)
        delta_t = st.session_state.cooling_water_delta_t
        required_flow_rate = (total_heat_to_reject_ramp / (4186 * delta_t)) * 60 if delta_t > 0 else 0
        st.metric("필요 냉각수 유량", f"{required_flow_rate:.2f} LPM")

with col_cool_res2:
    st.markdown("##### 💧 온도 유지 시")
    if cooling_type == '공냉식':
        st.metric("총 발열량", f"{total_heat_to_reject_soak / 1000:.2f} kW", help=f"({(total_heat_to_reject_soak * 3.41):,.0f} BTU/h)")
    elif cooling_type == '수냉식':
        delta_t = st.session_state.cooling_water_delta_t
        required_flow_rate = (total_heat_to_reject_soak / (4186 * delta_t)) * 60 if delta_t > 0 else 0
        st.metric("필요 냉각수 유량", f"{required_flow_rate:.2f} LPM")

st.info("💡 위 계산은 설정된 모든 부하와 온도별 성능 계수(COP)를 반영한 결과입니다.")
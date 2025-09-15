import streamlit as st
import numpy as np
import math

# --- 0. 기본 설정 ---
st.set_page_config(layout="wide")
st.title("🔌 챔버 설정 및 계산")
st.info("이 페이지에서 입력한 모든 사양은 다른 페이지의 계산에 연동됩니다.")

# --- 1. st.session_state 초기화 ---
def initialize_chamber_specs():
    """앱 세션에서 사용할 모든 변수들의 기본값을 설정합니다."""
    defaults = {
        'chamber_w': 1000, 'chamber_d': 1000, 'chamber_h': 1000,
        'insulation_type': '우레탄폼', 'insulation_thickness': 100,
        'sus_thickness': 1.2,
        'min_temp_spec': -10.0, 'max_temp_spec': 40.0, 'target_temp': 25.0,
        'outside_temp': 25.0,
        'fan_motor_load': 2.0, 'fan_soak_factor': 30,
        'load_type': '없음', 'num_cells': 4, 'cell_size': '211Ah (현대차 규격)',
        'ramp_rate': 1.0,
        'refrigeration_system': '1원 냉동',
        'actual_hp_1stage': 5.0, 'actual_rated_power_1stage': 3.5,
        'actual_hp_2stage_h': 3.0, 'actual_hp_2stage_l': 2.0,
        'actual_rated_power_2stage_h': 2.0, 'actual_rated_power_2stage_l': 1.5,
        'cooling_type': '공냉식', 'cooling_water_delta_t': 5.0,
        'safety_factor': 1.5
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- 콜백 함수 정의 ---
def update_fan_recommendation():
    """챔버 크기가 변경될 때 팬/모터 부하 추천값을 업데이트합니다."""
    volume_m3 = (st.session_state.chamber_w * st.session_state.chamber_d * st.session_state.chamber_h) / 1_000_000_000
    if volume_m3 < 1: st.session_state.fan_motor_load = 0.5
    elif 1 <= volume_m3 < 8: st.session_state.fan_motor_load = 1.5
    else: st.session_state.fan_motor_load = 2.5

# 앱 시작 시 초기화 함수 실행
initialize_chamber_specs()

# --- 2. 데이터 정의 ---
K_VALUES = {"우레탄폼": 0.023, "글라스울": 0.040, "세라크울": 0.150}
DENSITY_SUS = 7930
COP_TABLE_1STAGE = {10: 4.0, 0: 3.0, -10: 2.2, -20: 1.5, -25: 1.2}
COP_TABLE_2STAGE = {-20: 2.5, -30: 2.0, -40: 1.5, -50: 1.1, -60: 0.8, -70: 0.5}

# --- 3. UI 구성 ---
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
c2.number_input("목표 운전 온도 (°C)", min_value=st.session_state.min_temp_spec, max_value=st.session_state.max_temp_spec, step=1.0, format="%.1f", key='target_temp')
c3.number_input("외부 설정 온도 (°C)", step=1.0, format="%.1f", key='outside_temp')

st.subheader("3. 내부 부하")
c1, c2 = st.columns(2)
c1.number_input("팬/모터 정격 부하 (kW)", key='fan_motor_load', format="%.2f", help="챔버 크기를 변경하면 자동 추천값이 업데이트됩니다.")
c2.slider("온도 유지 시 팬/모터 부하율 (%)", 0, 100, key='fan_soak_factor')
st.selectbox("제품 부하 종류", options=['없음', '각형 배터리'], key='load_type')
if st.session_state.load_type == '각형 배터리':
    c1, c2 = st.columns(2)
    c1.number_input("챔버 내 셀 개수", min_value=1, step=1, key='num_cells')
    c2.selectbox("셀 사이즈 선택", options=['211Ah (현대차 규격)', '기타'], key='cell_size') # <- 차후 수정/추가

st.subheader("4. 온도 변화 속도")
st.number_input("목표 온도 변화 속도 (°C/min)", key='ramp_rate', step=0.1, format="%.1f")

st.subheader("5. 냉동 방식 및 실제 사양")
st.selectbox("설치된 냉동 방식", options=['1원 냉동', '2원 냉동'], key='refrigeration_system')
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
c1, c2 = st.columns(2)
c1.selectbox("냉각 방식", options=['공냉식', '수냉식'], key='cooling_type')
if st.session_state.cooling_type == '수냉식':
    c2.number_input("냉각수 설계 온도차 (ΔT, °C)", min_value=0.1, step=0.1, format="%.1f", key='cooling_water_delta_t')

st.markdown("---")

# --- 4. 자동 계산 로직 ---
st.subheader("자동 계산 결과")
st.slider("안전율 (Safety Factor)", 1.0, 3.0, key='safety_factor', help="계산된 총 열부하에 적용할 안전율입니다.")

# st.session_state에서 모든 최신 값 가져오기
specs = st.session_state

# 모든 부하 계산 (변수 할당)
k_value = K_VALUES.get(specs.insulation_type, 0.023)
thickness_m = specs.insulation_thickness / 1000.0
U_value = (k_value / thickness_m) if thickness_m > 0 else 0
A = 2 * ((specs.chamber_w * specs.chamber_d) + (specs.chamber_w * specs.chamber_h) + (specs.chamber_d * specs.chamber_h)) / 1_000_000
delta_T = abs(specs.target_temp - specs.outside_temp)
conduction_load_w = U_value * A * delta_T

sus_volume_m3 = A * (specs.sus_thickness / 1000.0)
calculated_internal_mass = sus_volume_m3 * DENSITY_SUS

volume_m3 = (specs.chamber_w * specs.chamber_d * specs.chamber_h) / 1_000_000_000
ramp_rate_c_per_sec = specs.ramp_rate / 60.0
air_load_w = (volume_m3 * 1.225) * 1005 * ramp_rate_c_per_sec
internal_mass_load_w = calculated_internal_mass * 500 * ramp_rate_c_per_sec
ramp_load_w = air_load_w + internal_mass_load_w

internal_product_load_w = specs.num_cells * 50.0 if specs.load_type == '각형 배터리' else 0.0
fan_motor_load_w_ramp = specs.fan_motor_load * 1000
fan_motor_load_w_soak = fan_motor_load_w_ramp * (specs.fan_soak_factor / 100.0)

total_heat_load_ramp = conduction_load_w + ramp_load_w + internal_product_load_w + fan_motor_load_w_ramp
total_heat_load_soak = conduction_load_w + internal_product_load_w + fan_motor_load_w_soak

# COP 및 최종 소비 전력 예측
if specs.target_temp > -25:
    operating_system = "1원 냉동 (작동 중)"; sorted_cop_items = sorted(COP_TABLE_1STAGE.items())
else:
    operating_system = "2원 냉동 (작동 중)"; sorted_cop_items = sorted(COP_TABLE_2STAGE.items())

cop_temps = np.array([item[0] for item in sorted_cop_items])
cop_values = np.array([item[1] for item in sorted_cop_items])
cop = np.interp(specs.target_temp, cop_temps, cop_values)

required_electrical_power_ramp = total_heat_load_ramp / cop if cop > 0 else float('inf')
required_hp_ramp = (required_electrical_power_ramp * specs.safety_factor) / 746
required_electrical_power_soak = total_heat_load_soak / cop if cop > 0 else float('inf')
required_hp_soak = (required_electrical_power_soak * specs.safety_factor) / 746

actual_hp, actual_rated_power = 0, 0
if specs.refrigeration_system == '1원 냉동':
    actual_hp = specs.actual_hp_1stage; actual_rated_power = specs.actual_rated_power_1stage
elif specs.refrigeration_system == '2원 냉동':
    if operating_system == "1원 냉동 (작동 중)":
        actual_hp = specs.actual_hp_2stage_h; actual_rated_power = specs.actual_rated_power_2stage_h
    else:
        actual_hp = specs.actual_hp_2stage_h + specs.actual_hp_2stage_l
        actual_rated_power = specs.actual_rated_power_2stage_h + specs.actual_rated_power_2stage_l

load_factor_ramp = required_hp_ramp / actual_hp if actual_hp > 0 else 0
estimated_power_ramp_kw = actual_rated_power * load_factor_ramp
load_factor_soak = required_hp_soak / actual_hp if actual_hp > 0 else 0
estimated_power_soak_kw = actual_rated_power * load_factor_soak

total_consumption_ramp = estimated_power_ramp_kw + specs.fan_motor_load
total_consumption_soak = estimated_power_soak_kw + (specs.fan_motor_load * (specs.fan_soak_factor / 100.0))

# --- 5. 결과 표시 ---
st.markdown("---")
st.subheader("✔️ 최종 소비 전력 예측")
st.info(f"선택된 시스템: **{specs.refrigeration_system}** | 현재 작동 방식: **{operating_system}** (목표 온도 {specs.target_temp}°C 기준)")
c1, c2 = st.columns(2)
with c1:
    st.markdown("##### 🌡️ 온도 변화 시")
    st.metric("총 열부하", f"{total_heat_load_ramp:.2f} W")
    st.metric("최소 필요 마력 (HP)", f"{required_hp_ramp:.2f} HP")
    st.metric("예상 부하율", f"{load_factor_ramp:.1%}")
    st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_ramp:.2f} kW")
with c2:
    st.markdown("##### 💧 온도 유지 시")
    st.metric("총 열부하", f"{total_heat_load_soak:.2f} W")
    st.metric("최소 필요 마력 (HP)", f"{required_hp_soak:.2f} HP")
    st.metric("예상 부하율", f"{load_factor_soak:.1%}")
    st.metric("챔버 전체 예상 소비 전력", f"{total_consumption_soak:.2f} kW")

if load_factor_ramp > 1.0:
    st.warning("경고: '온도 변화 시' 필요 마력이 실제 장비의 마력보다 큽니다. 장비 용량이 부족할 수 있습니다.")

# --- 6. 냉각 시스템 요구 사양 ---
st.markdown("---")
st.subheader("❄️ 냉각 시스템 요구 사양")
total_heat_to_reject_ramp = total_heat_load_ramp + (estimated_power_ramp_kw * 1000)
total_heat_to_reject_soak = total_heat_load_soak + (estimated_power_soak_kw * 1000)
c1, c2 = st.columns(2)
with c1:
    st.markdown("##### 🌡️ 온도 변화 시")
    if specs.cooling_type == '공냉식':
        st.metric("총 발열량", f"{total_heat_to_reject_ramp / 1000:.2f} kW", help=f"({(total_heat_to_reject_ramp * 3.41):,.0f} BTU/h)")
    elif specs.cooling_type == '수냉식':
        required_flow_rate = (total_heat_to_reject_ramp / (4186 * specs.cooling_water_delta_t)) * 60 if specs.cooling_water_delta_t > 0 else 0
        st.metric("필요 냉각수 유량", f"{required_flow_rate:.2f} LPM")
with c2:
    st.markdown("##### 💧 온도 유지 시")
    if specs.cooling_type == '공냉식':
        st.metric("총 발열량", f"{total_heat_to_reject_soak / 1000:.2f} kW", help=f"({(total_heat_to_reject_soak * 3.41):,.0f} BTU/h)")
    elif specs.cooling_type == '수냉식':
        required_flow_rate = (total_heat_to_reject_soak / (4186 * specs.cooling_water_delta_t)) * 60 if specs.cooling_water_delta_t > 0 else 0
        st.metric("필요 냉각수 유량", f"{required_flow_rate:.2f} LPM")

# --- 7. 설정값 저장 버튼 ---
if st.button("저장하기"):
    st.session_state["chamber_specs"] = {
        # 기본 입력값
        "chamber_w": specs.chamber_w,
        "chamber_d": specs.chamber_d,
        "chamber_h": specs.chamber_h,
        "insulation_type": specs.insulation_type,
        "insulation_thickness": specs.insulation_thickness,
        "target_temp": specs.target_temp,
        "outside_temp": specs.outside_temp,
        "load_type": specs.load_type,
        "num_cells": specs.num_cells,
        "fan_motor_load": specs.fan_motor_load,   # kW 단위
        "fan_soak_factor": specs.fan_soak_factor,
        "sus_thickness": specs.sus_thickness,
        "ramp_rate": specs.ramp_rate,
        "refrigeration_system": specs.refrigeration_system,
        "safety_factor": specs.safety_factor,

        # 계산된 값
        "U_value": U_value,
        "surface_area": A,
        "chamber_volume": volume_m3,
        "conduction_load_w": conduction_load_w,
        "ramp_load_w": ramp_load_w,
        "internal_product_load_w": internal_product_load_w,
        "fan_motor_load_w_ramp": fan_motor_load_w_ramp,
        "fan_motor_load_w_soak": fan_motor_load_w_soak,
        "total_heat_load_ramp": total_heat_load_ramp,
        "total_heat_load_soak": total_heat_load_soak,
    }
    st.success("챔버 사양이 저장되었습니다 ✅ (챔버 온도 프로파일 페이지에서 불러올 수 있습니다)")
import win32com.client
import re
import os
import shutil


def add_steady_flow_profile(
    project_path: str,
    base_profile: str,
    multiplier: float,
    new_profile_name: str
):
    # ── 1. 프로파일 목록 확인 (COM) ───────────────────────────────────────────
    rc = win32com.client.Dispatch("RAS67.HECRASController")
    rc.Project_Open(project_path)

    n_profiles = 0
    profile_names = []
    n_profiles, profile_names = rc.Output_GetProfiles(n_profiles, profile_names)
    profile_names = list(profile_names)
    print(f"[정보] 현재 프로파일 목록: {profile_names}")
    rc.QuitRas()

    if base_profile not in profile_names:
        raise ValueError(f"기준 프로파일 '{base_profile}'을 찾을 수 없습니다.")

    # 이미 추가된 경우 중단
    if new_profile_name in profile_names:
        raise ValueError(f"'{new_profile_name}'이 이미 존재합니다. 프로파일 목록: {profile_names}")

    base_idx = profile_names.index(base_profile)  # 0-based

    # ── 2. Flow 파일 경로 찾기 ────────────────────────────────────────────────
    proj_dir  = os.path.dirname(project_path)
    proj_stem = os.path.splitext(os.path.basename(project_path))[0]

    flow_filename_raw = None
    with open(project_path, "r") as f:
        for line in f:
            if line.startswith("Flow File="):
                flow_filename_raw = line.strip().split("=", 1)[1].strip()
                break

    if not flow_filename_raw:
        raise ValueError("프로젝트 파일에 'Flow File=' 항목이 없습니다.")

    composed = flow_filename_raw if "." in flow_filename_raw else f"{proj_stem}.{flow_filename_raw}"
    flow_file_path = os.path.join(proj_dir, composed)

    if not os.path.exists(flow_file_path):
        raise FileNotFoundError(f"Flow 파일을 찾을 수 없습니다: {flow_file_path}")

    print(f"[정보] Flow 파일 경로: {flow_file_path}")

    # ── 3. 파일 파싱 ──────────────────────────────────────────────────────────
    with open(flow_file_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Number of Profiles 수정
        if re.match(r"Number of Profiles\s*=", line):
            new_lines.append(f"Number of Profiles= {n_profiles + 1}\n")
            i += 1
            continue

        # ── Profile Names: 중복 없이 추가
        if re.match(r"Profile Names\s*=", line):
            existing_names = line.strip().split("=", 1)[1].strip()
            # 혹시 이전 실행으로 중복된 PF10 제거 후 다시 추가
            clean_names = ",".join(
                n for n in existing_names.split(",") if n != new_profile_name
            )
            new_lines.append(f"Profile Names={clean_names},{new_profile_name}\n")
            i += 1
            continue

        # ── River Rch & RM= 다음 줄이 유량값 행
        if line.startswith("River Rch & RM="):
            new_lines.append(line)
            i += 1

            # 다음 줄: 공백으로 구분된 숫자들
            if i < len(lines):
                val_line = lines[i]
                vals = val_line.split()

                try:
                    base_val = float(vals[base_idx])
                    new_val  = int(round(base_val * multiplier))
                except (IndexError, ValueError):
                    new_val = 0
                    print(f"[경고] 유량값 파싱 실패: {val_line.strip()}")

                # 기존 값 유지 + 새 값을 같은 포맷(8자 폭)으로 추가
                new_val_str = f"{new_val:8d}"
                new_lines.append(val_line.rstrip("\n") + new_val_str + "\n")
                i += 1
            continue

        # ── Boundary 프로파일 번호 수정 (기존 9개 → 10개로 늘어나므로 불필요하지만 안전하게 유지)
        new_lines.append(line)
        i += 1

    # ── 4. 백업 후 저장 ───────────────────────────────────────────────────────
    backup_path = flow_file_path + ".bak"
    shutil.copy2(flow_file_path, backup_path)
    print(f"[정보] 백업 완료: {backup_path}")

    with open(flow_file_path, "w") as f:
        f.writelines(new_lines)

    print(f"[완료] '{new_profile_name}' 프로파일이 추가되었습니다.")
    print(f"       기준: {base_profile}  ×  {multiplier}  ({multiplier*100:.0f}%)")


if __name__ == "__main__":
    add_steady_flow_profile(
        project_path     = r"C:\Hriver\beforeLSB\hwangriver.prj",
        base_profile     = "20yr",
        multiplier       = 1.2,
        new_profile_name = "PF10"
    )
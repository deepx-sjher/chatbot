#!/usr/bin/env python3
"""
generate_lst.py
---------------
프로젝트 루트를 순회하며 lst.txt 를 작성합니다.
- .lstignore   : .gitignore 와 동일한 패턴 문법
- lst.txt      : <상대/경로/파일> …소스… </상대/경로/파일>  형식 (UTF-8)
                 맨 앞에 필터링된 파일 트리를 포함합니다.
사용 예
    python generate_lst.py           # 현재 디렉터리 기준
    python generate_lst.py /path/src  # 특정 루트 지정
"""
from __future__ import annotations
import argparse
import io
import os
import sys
from pathlib import Path
from typing import Set, List, Tuple
try:
    import pathspec  # type: ignore
except ImportError as exc:
    sys.exit("pathspec 모듈이 필요합니다.  `pip install pathspec` 후 다시 시도하세요.") # noqa: E501
# -----------------------------------------------------------
# 내부 함수
# -----------------------------------------------------------
def load_ignore_file(root: Path) -> "pathspec.PathSpec":
    """프로젝트 루트에서 .lstignore 를 읽어 PathSpec 객체 반환."""
    ignore_file = root / ".lstignore"
    patterns = []
    if ignore_file.is_file(): # Check if it's a file, not a directory
        print(f"정보: {ignore_file.relative_to(root)} 파일을 사용합니다.")
        patterns = ignore_file.read_text(encoding="utf-8").splitlines()
    else:
        print("정보: .lstignore 파일이 없어 모든 파일을 포함합니다.")
    # 기본적으로 무시할 패턴 추가 (예: .git, lst.txt 자체)
    default_ignores = [".git/", ".lstignore", "lst.txt"] # lst.txt 자체를 무시목록에 추가
    # 사용자가 지정한 출력 파일 이름도 무시 목록에 추가해야 할 수 있음
    # 여기서는 기본값인 lst.txt만 추가
    patterns.extend(default_ignores)
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
def is_binary(path: Path, blocksize: int = 1024) -> bool:
    """간단한 바이너리 판별: NUL 바이트 포함 여부."""
    if not path.is_file(): # Ensure it's a file before trying to open
        return False # Directories are not binary in this context
    try:
        with path.open("rb") as f:
            return b"\0" in f.read(blocksize)
    except Exception as e:
        print(f"경고: 파일을 읽는 중 오류 발생 ({path.relative_to(path.parent)}): {e}", file=sys.stderr)
        return True  # 읽기 실패 시 바이너리 취급
def get_filtered_paths(root: Path, spec: "pathspec.PathSpec") -> Set[Path]:
    """
    루트를 순회하며 ignore 되지 않고 바이너리가 아닌 파일 및
    해당 파일들을 포함하는 디렉토리들의 상대 경로 Set을 반환합니다.
    """
    included_relative_paths: Set[Path] = set()
    output_filename = "lst.txt" # 기본 출력 파일 이름 (명령줄 인자에서 가져올 수도 있음)
    for path in root.rglob("*"):
        try:
            relative_path = path.relative_to(root)
        except ValueError:
            # root 외부에 있는 심볼릭 링크 등 예외 처리
            continue
        # pathspec은 디렉토리에도 적용될 수 있음
        if spec.match_file(str(relative_path)) or spec.match_file(str(relative_path) + '/'):
            continue
        # 출력 파일 자체는 포함하지 않음 (load_ignore_file 에서도 처리하지만 여기서 한번 더 확인)
        if path.name == output_filename and path.parent == root:
             continue
        if path.is_file():
            if not is_binary(path):
                # 파일이 포함되면 파일 자체와 모든 상위 디렉토리를 포함 Set에 추가
                included_relative_paths.add(relative_path)
                current = relative_path.parent
                while str(current) != '.':
                    included_relative_paths.add(current)
                    current = current.parent
                # 루트 디렉토리 ('.') 표현을 위해 추가 (필요 시)
                # included_relative_paths.add(Path('.'))
        elif path.is_dir():
            # 디렉토리는 그 안에 포함될 파일이 있을 때만 추가됨 (위 로직에서 처리)
            pass
    return included_relative_paths
def generate_tree_string(root: Path, spec: "pathspec.PathSpec") -> str:
    """
    필터링된 파일 및 디렉토리 목록을 기반으로 파일 트리 문자열을 생성합니다.
    """
    included_relative_paths = get_filtered_paths(root, spec)
    if not included_relative_paths:
        return f"{root.name}/\n(포함할 파일 또는 디렉토리가 없습니다.)\n"
    # pathlib.Path 객체를 문자열로 변환하여 사용 (정렬 및 비교 용이)
    # 또한 parts를 사용하기 위해 Path 객체 리스트 유지
    sorted_paths: List[Path] = sorted(list(included_relative_paths))
    tree_lines: List[str] = [f"{root.name}/"]
    path_pointers: Dict[Path, bool] = {path: True for path in sorted_paths} # 각 경로가 마지막 항목인지 추적
    # 어떤 경로가 부모 디렉토리 내에서 마지막 항목인지 미리 계산
    last_items: Set[Path] = set()
    parent_map: Dict[Path, List[Path]] = {}
    for path in sorted_paths:
        parent = path.parent
        if parent not in parent_map:
            parent_map[parent] = []
        parent_map[parent].append(path)
    for parent, children in parent_map.items():
        if children:
            last_items.add(children[-1]) # 각 부모별 마지막 자식 항목 추가
    for i, path in enumerate(sorted_paths):
        depth = len(path.parts)
        prefix = ""
        for j in range(depth - 1):
            # 상위 경로가 해당 레벨에서 마지막 항목인지 확인
            ancestor = Path(*path.parts[:j+1])
            # 이 조상 경로가 형제들 중 마지막인지 확인해야 함
            # 이를 위해선 전체 구조를 알아야 함 -> last_items 사용
            parent_of_ancestor = ancestor.parent
            siblings_of_ancestor = parent_map.get(parent_of_ancestor, [])
            # ancestor가 형제들 중 마지막인가?
            is_last_ancestor = siblings_of_ancestor and ancestor == siblings_of_ancestor[-1]
            if ancestor in last_items : # Check if the ancestor itself is a last item among its siblings
                 prefix += "    "
            else:
                 prefix += "│   "
        connector = "└── " if path in last_items else "├── "
        tree_lines.append(f"{prefix}{connector}{path.name}")
    return "\n".join(tree_lines)
def iter_source_files(root: Path, spec: "pathspec.PathSpec"):
    """
    루트를 재귀 순회하며 ignore 되지 않는 *파일* Path 와 상대경로 이터레이터.
    """
    for path in root.rglob("*"):
        # Ensure path is within root, handling symlinks potentially outside
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue # Skip paths not relative to root
        # 디렉토리는 건너뜀 (파일만 처리)
        if path.is_dir():
            continue
        # 파일 ignore 판단 (디렉토리 ignore는 rglob가 처리하지 않으므로 pathspec으로 확인)
        # 파일 경로 자체 또는 상위 디렉토리가 무시되는지 확인
        if spec.match_file(str(rel)):
             continue
        # .lstignore 파일 자체도 무시
        if path.name == ".lstignore" and path.parent == root:
            continue
        # 출력 파일 자체도 무시 (여기서 다시 확인)
        output_filename = "lst.txt" # TODO: Get from args if possible
        if path.name == output_filename and path.parent == root:
            continue
        yield path, rel
def write_lst(root: Path, outfile: Path, spec: "pathspec.PathSpec", tree_string: str) -> None:
    """lst.txt 파일 작성 (파일 트리 포함)."""
    print(f"정보: 출력 파일 '{outfile.relative_to(Path.cwd())}' 생성 중...")
    try:
        with outfile.open("w", encoding="utf-8", newline="\n") as out:
            # 1. 파일 트리 작성
            out.write("File Tree:\n")
            out.write(tree_string)
            out.write("\n\n---\n\n") # 구분선 추가
            # 2. 파일 내용 작성
            written_files_count = 0
            skipped_binary_count = 0
            skipped_encoding_count = 0
            for path, rel in iter_source_files(root, spec):
                if is_binary(path):
                    # 바이너리 파일은 건너뜀
                    print(f"정보: 바이너리 파일 건너뜀 - {rel}")
                    skipped_binary_count += 1
                    continue
                try:
                    # UTF-8로 읽기 시도
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    try:
                        # 다른 인코딩으로 시도 (예: cp949 for Windows Korean)
                        content = path.read_text(encoding="cp949")
                        print(f"정보: UTF-8 읽기 실패, cp949로 읽음 - {rel}")
                    except Exception as e:
                        # 다른 인코딩도 실패하면 건너뜀
                        print(f"경고: 인코딩 오류로 파일 건너뜀 - {rel}: {e}", file=sys.stderr)
                        skipped_encoding_count += 1
                        continue
                except Exception as e:
                    print(f"경고: 파일 읽기 오류로 건너뜀 - {rel}: {e}", file=sys.stderr)
                    skipped_encoding_count += 1
                    continue
                tag = str(rel).replace("\\", "/")  # Windows 경로 보정
                out.write(f"<{tag}>\n")
                out.write(content)
                # 파일 끝에 개행 없으면 LLM 파싱에 문제될 수 있으니 보정
                if not content.endswith("\n"):
                    out.write("\n")
                out.write(f"</{tag}>\n\n") # 파일 간 간격 추가
                written_files_count += 1
        print(f"정보: 총 {written_files_count}개 파일 처리 완료.")
        if skipped_binary_count > 0:
            print(f"정보: 바이너리 파일 {skipped_binary_count}개 건너뜀.")
        if skipped_encoding_count > 0:
            print(f"정보: 인코딩 문제 또는 읽기 오류로 {skipped_encoding_count}개 파일 건너뜀.")
    except Exception as e:
        print(f"오류: 출력 파일 작성 중 문제 발생 - {e}", file=sys.stderr)
        # 부분적으로 작성된 파일 삭제 시도
        if outfile.exists():
            try:
                outfile.unlink()
            except Exception as unlink_e:
                print(f"경고: 부분 작성된 파일 삭제 실패 - {unlink_e}", file=sys.stderr)
        sys.exit(1)
# -----------------------------------------------------------
# CLI
# -----------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="프로젝트 파일을 모아 lst.txt 를 생성합니다. 파일 트리를 포함하며, .lstignore 규칙을 따릅니다.",
        formatter_class=argparse.RawTextHelpFormatter # Docstring 포맷 유지
    )
    p.add_argument(
        "root",
        nargs="?",
        default=".",
        type=Path,
        help="프로젝트 루트 디렉터리 (기본값: 현재 디렉터리)",
    )
    p.add_argument(
        "-o",
        "--output",
        default="lst.txt",
        # type=Path 를 사용하면 상대경로 입력 시 현재 작업 디렉토리 기준으로 Path 객체가 생성됨
        # resolve() 를 나중에 호출하여 절대 경로로 만드는 것이 좋음
        type=str,
        help="출력 파일 경로 (기본값: lst.txt)",
    )
    return p.parse_args()
def main() -> None:
    args = parse_args()
    # 입력된 root 경로 처리
    try:
        root: Path = Path(args.root).resolve(strict=True) # strict=True 로 존재하지 않으면 에러
    except FileNotFoundError:
        print(f"오류: 지정된 루트 디렉터리를 찾을 수 없습니다: {args.root}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"오류: 루트 디렉터리 처리 중 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    if not root.is_dir():
         print(f"오류: 지정된 경로는 디렉터리가 아닙니다: {root}", file=sys.stderr)
         sys.exit(1)
    # 출력 파일 경로 처리 (현재 작업 디렉토리 기준 상대 경로 가능하도록)
    outfile: Path = Path(args.output)
    # 만약 outfile이 절대 경로가 아니라면, 현재 작업 디렉토리 기준으로 만듦
    if not outfile.is_absolute():
        outfile = Path.cwd() / outfile
    # 출력 디렉토리가 없으면 생성 시도
    try:
        outfile.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"오류: 출력 디렉토리 생성 실패 ({outfile.parent}): {e}", file=sys.stderr)
        sys.exit(1)
    print(f"루트 디렉터리: {root}")
    print(f"출력 파일: {outfile}")
    # .lstignore 로드 및 pathspec 생성
    # 출력 파일 이름을 load_ignore_file에 전달하여 무시 목록에 동적으로 추가
    spec = load_ignore_file(root) # 출력 파일 이름 자체는 load_ignore_file에서 처리하도록 개선함
    # 파일 트리 생성
    print("정보: 파일 트리 생성 중...")
    try:
        tree_string = generate_tree_string(root, spec)
        print(tree_string) # 생성된 트리 콘솔에도 출력
    except Exception as e:
        print(f"오류: 파일 트리 생성 중 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    # lst.txt 파일 작성
    write_lst(root, outfile, spec, tree_string)
    try:
        rel_out = outfile.relative_to(Path.cwd())
    except ValueError:
        rel_out = outfile # 현재 작업 디렉토리 외부에 있으면 절대 경로 표시
    print(f"\n:흰색_확인_표시: 생성 완료: {rel_out}")
if __name__ == "__main__":
    main()
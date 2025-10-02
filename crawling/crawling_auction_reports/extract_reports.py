import argparse
import os
import sys

from .report_parser import parse_pdf_to_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="법원 경매 차량 감정평가서 PDF에서 정보/사진 추출"
    )
    default_pdf = os.path.join(
        os.path.dirname(__file__), "2024타경102980-1_감정평가서.pdf"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=default_pdf,
        help="분석할 PDF 경로 (기본: 예제 PDF)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="결과 저장 루트 디렉터리 (기본: PDF와 같은 폴더 하위 extracted)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
        return 1

    result = parse_pdf_to_output(args.pdf, output_root=args.out)
    print("추출 완료")
    print({
        "pdf": result.pdf_filename,
        "location": result.location_address,
        "appraisal_type": result.appraisal.type,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())



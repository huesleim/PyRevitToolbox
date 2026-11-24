import argparse
import sys

from dwg_merger.pipeline import ConverterNotFoundError, merge_folder


def report_progress(index, total, filename):
    print(f"[{index}/{total}] {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Merge a folder of sheet DWGs into one DWG, one layout per sheet."
    )
    parser.add_argument("input_folder", help="Folder containing the source .dwg files")
    parser.add_argument("output_dwg", help="Path to write the merged .dwg to")
    args = parser.parse_args()

    try:
        result = merge_folder(args.input_folder, args.output_dwg, progress_callback=report_progress)
    except ConverterNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Done: {result}")


if __name__ == "__main__":
    main()

"""Use the optional packaged Tesseract engine without a system installation."""
import sys

from tesserocr import PyTessBaseAPI


def main():
    with PyTessBaseAPI(path=sys.argv[2], lang="eng") as engine:
        engine.SetImageFile(sys.argv[1])
        engine.Recognize()
        sys.stdout.reconfigure(encoding="utf-8")
        print("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext")
        print(engine.GetTSVText(0))


if __name__ == "__main__":
    main()

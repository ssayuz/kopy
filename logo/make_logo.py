"""kopy 로고 만들기: logo.png (512px), kopy.ico (윈도우 아이콘)

필요: python -m pip install pillow
"""

import os

from PIL import Image, ImageDraw, ImageFont

여기 = os.path.dirname(os.path.abspath(__file__))
크기 = 1024
글꼴 = r"C:\Windows\Fonts\times.ttf"  # Times New Roman

배경색 = (17, 17, 17)
글자색 = (245, 243, 238)


def 그리기():
    그림 = Image.new("RGBA", (크기, 크기), (0, 0, 0, 0))
    펜 = ImageDraw.Draw(그림)
    펜.rounded_rectangle((0, 0, 크기 - 1, 크기 - 1), radius=200, fill=배경색)

    글자 = "kopy"
    폰트 = ImageFont.truetype(글꼴, 400)
    # 가로 폭이 그림의 76%가 되도록 글자 크기 맞추기
    상자 = 펜.textbbox((0, 0), 글자, font=폰트)
    폰트 = ImageFont.truetype(글꼴, round(400 * 크기 * 0.76 / (상자[2] - 상자[0])))
    # 가운데 정렬: x-높이(x, o 높이) 기준으로 맞춰야 눈으로 봤을 때 가운데
    상자 = 펜.textbbox((0, 0), 글자, font=폰트)
    x높이 = 펜.textbbox((0, 0), "o", font=폰트)
    x = (크기 - (상자[2] - 상자[0])) / 2 - 상자[0]
    y = (크기 - (x높이[3] - x높이[1])) / 2 - x높이[1]
    펜.text((x, y), 글자, font=폰트, fill=글자색)
    return 그림


if __name__ == "__main__":
    로고 = 그리기()
    로고.resize((512, 512), Image.LANCZOS).save(os.path.join(여기, "logo.png"))
    로고.save(os.path.join(여기, "kopy.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("완료: logo.png, kopy.ico")

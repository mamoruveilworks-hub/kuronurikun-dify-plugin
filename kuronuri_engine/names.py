# This file is copied from the Kuronuri-kun API (app/names.py) by tools/sync_plugin_engine.py.
# Do not edit it here; edit the original and run the script again.
"""氏名の辞書（よくある姓・名）。rules.detect_person_by_dictionary で使う。

辞書は「よくある姓と名」を運営者が書き起こしたもの。網羅はしていないので、珍しい名前は見つけられない。
足りない名前は、ここに追記すればそのまま使われる（空白・改行区切り）。

- SURNAMES      … 2文字以上の姓。単独でも「〇〇です」「〇〇と申します」などの文脈があれば氏名とみなす
- SHORT_SURNAMES… 1文字の姓（林・森など）。地名や普通の言葉と紛らわしいので、名と組み合わさったとき
                   か、自己紹介の文脈があるときだけ使う
- GIVEN_NAMES   … 名
- ROMAJI_SURNAMES … ローマ字の姓（「Taro Yamada」「YAMADA Taro」）
"""

from __future__ import annotations


def _words(s: str) -> frozenset[str]:
    return frozenset(s.split())


_ALL_SURNAMES = _words("""
佐藤 鈴木 高橋 田中 伊藤 渡辺 山本 中村 小林 加藤 吉田 山田 佐々木 山口 松本 井上 木村 斎藤 清水
山崎 池田 橋本 阿部 石川 山下 中島 石井 小川 前田 岡田 長谷川 藤田 後藤 近藤 村上 遠藤 青木 坂本
斉藤 福田 太田 西村 藤井 金子 岡本 藤原 中野 三浦 原田 中川 松田 竹内 小野 田村 中山 和田 石田
森田 上田 柴田 酒井 工藤 横山 宮崎 宮本 内田 高木 安藤 島田 谷口 大野 高田 丸山 今井 河野 藤本
村田 武田 上野 杉山 増田 小山 平野 大塚 千葉 久保 松井 小島 岩崎 桜井 野口 松尾 野村 木下 菊地
佐野 大西 杉本 新井 浜田 菅原 市川 水野 小松 山内 西田 菊池 西川 五十嵐 北村 安田 中田 川口
平田 川崎 飯田 吉川 本田 久保田 沢田 吉村 渡部 岩田 中西 服部 樋口 福島 川上 永井 松岡 田口
山中 森本 土屋 矢野 広瀬 秋山 石原 松下 大橋 松浦 吉岡 小池 馬場 浅野 荒木 大久保 野田 小沢
田辺 川村 星野 黒田 尾崎 望月 永田 熊谷 内藤 松村 西山 大谷 平井 大島 岩本 片山 本間 早川 横田
岡崎 荒井 大石 鎌田 成田 宮田 小田 石橋 篠原 須藤 河合 大竹 篠田 高野 小西 堀内 大川 関口 上原
今村 古川 宮下 小坂 安部 西尾 坂口 松原 細川 北川 吉野 稲垣 平山 宇野 野崎 宮内 堀田 小原 中尾
大森 塚本 片岡 島村 根本 古田 栗原 大山 桑原 新田 西岡 北野 田島 竹田 角田 白石 高山 金井 藤川
福井 牧野 岡村 中谷 藤村 増井 青山 森下 三上 松山 菅野 井口 内山 山岸 小笠原 竹中 前川 奥村
川島 浅井 杉浦 安達 宮原 塩田 福本 島崎 荻野 水谷 吉井 秋元 北原 西野 堀江 田代 長田 豊田 浜口
奥田 田上 早瀬 黒川 森山 伊東 大川原 富田 高松 宮川 竹本 浅田 西本 岩井 長尾 中原 松永 中本
上村 坂井 川田 中嶋 三宅 大須賀 白井 大和田 南 結城 足立 堤 江口 寺田 庄司 稲葉 三好 二宮
内海 大坪 長井 大嶋 小倉 植田 堀口 米田 石崎 水田 有村 若林 江藤 片桐 柳田 秋田 川端 宮地
八木 金田 古賀 吉原 川合 磯部 村井 村松 岸本 坂田 清田 戸田 須田 野中 梅田 梅原 梅本 大内
安井 辻本 辻村 松谷 西原 東 宮城 有田 寺島 寺本 寺西 河村 河本 河田 栗田 栗山 芦田 浅川 中澤
渡邉 渡邊 渡部 齋藤 齊藤 髙橋 髙木 濱田 澤田 廣瀬 邊見 嶋田 嶌田 﨑山 山﨑 宮﨑 岩﨑 長﨑
櫻井 澤 瀬戸 瀬川 関根 伊達 坂上 坂下 川西 川本 細田 細井 細谷 竹下 竹村 岡野 岡部 今野 今田
小泉 小倉 小森 小谷 小山田 大木 大村 大沢 大澤 大場 大平 中井 中沢 中澤 藤沢
藤澤 藤岡 藤野 福永 福原 福山 石垣 石塚 石黒 宮澤 宮沢 野上 野沢 野澤 西沢 西澤 北沢 北澤
""")

_SHORT = _words("""
林 森 原 堀 関 辻 西 東 南 北 岡 島 平 星 泉 谷 浜 杉 桜 萩 柳 栗 菅 庄 秦 畑 堤 沖 塩 岩 坂 林
""")

# 1文字の姓は SHORT_SURNAMES に、2文字以上は SURNAMES に振り分ける
SURNAMES = frozenset(w for w in _ALL_SURNAMES if len(w) >= 2)
SHORT_SURNAMES = _SHORT | frozenset(w for w in _ALL_SURNAMES if len(w) == 1)

GIVEN_NAMES = _words("""
太郎 次郎 三郎 一郎 二郎 四郎 五郎 健 健太 健一 健二 健太郎 健司 健吾 翔 翔太 翔平 翔吾 大輔 大樹
大翔 大和 大地 大介 拓也 拓海 拓真 拓実 直樹 直人 直也 和也 和真 和樹 和人 和夫 和彦 和宏 達也
哲也 誠 誠一 亮 亮太 亮介 涼 涼太 蓮 湊 悠真 悠人 悠斗 陽翔 陽太 颯太 颯 隼人 優斗 優太 優 海斗
陸 樹 蒼 悠 晴 晴人 翼 剛 浩 浩二 浩之 浩一 博 博之 弘 隆 隆之 崇 茂 修 修平 学 勝 稔 進 豊 清
正 正樹 正人 正和 明 昭 晃 聡 敏 敏之 秀樹 秀人 英樹 雅人 雅之 雅也 康弘 康平 俊之 俊介 俊 慎吾
慎太郎 慎也 雄一 雄太 雄介 裕太 裕介 裕之 祐介 圭 圭介 啓介 恭平 航 航平 奏太 結翔 蒼空 陽向
一輝 一樹 一真 一平 智也 智之 智 光 渉 匠 仁 純 純一 拓 貴之 貴大 孝 孝之 伸也 伸一 真一 真也
信也 信之 義之 義人 克也 克彦 耕平 遼 遼太 瑛太 怜 律 新 暖 結人 碧 朝陽 惣太 樹生 光太郎 龍之介
龍 竜也 竜一 政人 勇気 勇太 勇人 友也 友樹 将太 将也 幸太 幸一 恵太 啓太 開 礼 純也 尚樹 尚人
花子 美咲 陽菜 結衣 葵 凛 芽依 結菜 さくら 美羽 彩 彩香 彩花 愛 愛子 恵 恵子 久美子 由美 由美子
真由美 明美 直美 智子 洋子 京子 幸子 和子 節子 典子 裕子 優子 陽子 美穂 美紀 美香 香織 沙織 詩織
麻衣 舞 真理 真理子 理恵 理沙 千尋 千夏 七海 菜々子 莉子 杏 杏奈 美月 美優 心春 結愛 紬 澪 楓 遥
春香 明日香 奈々 佳奈 加奈子 綾 綾香 瞳 薫 舞子 友美 亜美 亜希子 朋子 美由紀 由紀 由香 裕美 麻美
恵美 美奈子 真紀 真希 真奈美 桃子 桃香 菜摘 菜月 夏美 千春 千秋 小百合 百合子 百合 純子 順子
淳子 敦子 康子 靖子 弘子 博美 寛子 道子 美智子 美和 美保 美里 美緒 美奈 美帆 美玲 未来 未央
里奈 里美 梨花 莉奈 莉央 玲奈 怜奈 礼子 麗子 友香 友里 友子 有紀 有希 祐子 夕子 夕夏 優花 優奈
栞 茜 桜 咲 咲希 咲良 咲子 紗希 紗英 沙也加 沙耶 早紀 早苗 聖子 晴美 晴香 春菜 日向 ひなた 陽葵
芽生 萌 萌花 結子 結 一花 心 心愛 乃愛 柚 柚希 柚子 環 千恵 千絵 智美 智恵 知子 知美 奈緒 奈央
""")

ROMAJI_SURNAMES = frozenset(w.lower() for w in """
Sato Suzuki Takahashi Tanaka Ito Watanabe Yamamoto Nakamura Kobayashi Kato Yoshida Yamada Sasaki
Yamaguchi Matsumoto Inoue Kimura Hayashi Saito Shimizu Yamazaki Mori Ikeda Hashimoto Abe Ishikawa
Yamashita Nakajima Ishii Ogawa Maeda Okada Hasegawa Fujita Goto Kondo Murakami Endo Aoki Sakamoto
Fukuda Ota Nishimura Fujii Kaneko Okamoto Fujiwara Nakano Miura Harada Nakagawa Matsuda Takeuchi Ono
Tamura Nakayama Wada Ishida Morita Ueda Shibata Sakai Kudo Yokoyama Miyazaki Miyamoto Uchida Takagi
Ando Shimada Taniguchi Ohno Takada Maruyama Imai Kono Fujimoto Murata Takeda Ueno Sugiyama Masuda
Koyama Hirano Otsuka Chiba Kubo Matsui Kojima Iwasaki Sakurai Noguchi Matsuo Nomura Kinoshita Kikuchi
Sano Onishi Sugimoto Arai Hamada Sugawara Ichikawa Mizuno Komatsu Nishida Nishikawa Igarashi Kitamura
Yasuda Nakata Kawaguchi Hirata Kawasaki Iida Yoshikawa Honda Kubota Sawada Yoshimura Iwata Nakanishi
Hattori Higuchi Fukushima Kawakami Nagai Matsuoka Taguchi Yamanaka Morimoto Tsuchiya Yano Hirose
Akiyama Ishihara Matsushita Ohashi Matsuura Yoshioka Koike Baba Asano Araki Okubo Noda Ozawa Tanabe
Kawamura Hoshino Kuroda Ozaki Mochizuki Nagata Kumagai Naito Watabe Saitou Satou Itou Katou Gotou
""".split())

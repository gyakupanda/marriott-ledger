#!/usr/bin/env python3
"""
Googleスプレッドシートからデータを取得し、index.html に埋め込んで dist/ に出力する。
GitHub Actions から実行される。環境変数:
  SHEET_ID   (必須) スプレッドシートのID
  POINTS_GID (必須) Marriott_Raw タブのgid (例: 0)
  CASH_GID   (任意) Marriott_Raw_Cash タブのgid。未設定なら価格は埋め込まない
"""
import os, re, sys, urllib.request, pathlib

SHEET_ID = os.environ["SHEET_ID"]
POINTS_GID = os.environ.get("POINTS_GID", "0")
CASH_GID = os.environ.get("CASH_GID", "").strip()

def fetch_csv(gid: str) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read().decode("utf-8")
    if "<html" in data[:200].lower():
        raise RuntimeError(
            "CSVではなくHTMLが返されました。シートの共有設定が"
            "「リンクを知っている全員(閲覧者)」になっているか確認してください。"
        )
    return data

def js_escape(s: str) -> str:
    # テンプレートリテラルに安全に埋め込む
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

def inject(html: str, start: str, end: str, varname: str, csv_text: str) -> str:
    block = f"/*{start}*/\nconst {varname} = `{js_escape(csv_text)}`;\n/*{end}*/"
    pattern = re.compile(re.escape(f"/*{start}*/") + r".*?" + re.escape(f"/*{end}*/"), re.S)
    new_html, n = pattern.subn(lambda m: block, html)
    if n != 1:
        raise RuntimeError(
            f"マーカー {start} が見つかりません(index.htmlを確認)。"
            f"形式は /*{start}*/ です。"
        )
    return new_html

def main():
    points = fetch_csv(POINTS_GID)
    rows = points.count("\n")
    if rows < 2:
        print("ポイントデータが空です。前日のビルド結果を維持するため失敗扱いにします。", file=sys.stderr)
        sys.exit(1)
    print(f"points: {rows} 行取得")

    cash = ""
    if CASH_GID:
        try:
            cash = fetch_csv(CASH_GID)
            print(f"cash: {cash.count(chr(10))} 行取得")
        except Exception as e:
            print(f"価格データの取得に失敗(ポイントのみで続行): {e}", file=sys.stderr)

    html = pathlib.Path("index.html").read_text(encoding="utf-8")
    html = inject(html, "__POINTS_DATA_START__", "__POINTS_DATA_END__", "RAW_POINTS_CSV", points)
    html = inject(html, "__CASH_DATA_START__", "__CASH_DATA_END__", "RAW_CASH_CSV", cash)

    out = pathlib.Path("dist")
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"dist/index.html を出力 ({len(html):,} bytes)")

    # 単価ランキングページ(ranking.html)にも同じデータを埋め込んで出力する。
    # ranking.html はindex.htmlと同じマーカー方式なので、存在すれば同様に処理する。
    rank_src = pathlib.Path("ranking.html")
    if rank_src.exists():
        rhtml = rank_src.read_text(encoding="utf-8")
        rhtml = inject(rhtml, "__POINTS_DATA_START__", "__POINTS_DATA_END__", "RAW_POINTS_CSV", points)
        rhtml = inject(rhtml, "__CASH_DATA_START__", "__CASH_DATA_END__", "RAW_CASH_CSV", cash)
        (out / "ranking.html").write_text(rhtml, encoding="utf-8")
        print(f"dist/ranking.html を出力 ({len(rhtml):,} bytes)")
    else:
        print("ranking.html が無いためスキップ(index.htmlのみ出力)")

if __name__ == "__main__":
    main()

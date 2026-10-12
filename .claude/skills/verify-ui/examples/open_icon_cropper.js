// screenshot.py の --inject に渡す例。
// キャラクター画面(character.html)で、アイコン切り抜きウィンドウを開いた状態にする。
//
//   py -3 .claude/skills/verify-ui/scripts/screenshot.py --page character.html \
//       --inject .claude/skills/verify-ui/examples/open_icon_cropper.js --title --out cropper.png
//
//   --hash apply を付けると、OKを押した後（切り抜き結果がアイコンに入った状態）を撮る。
//
// 外部の画像ファイルを使わず、canvas でテスト用の画像を作っている。
// 測った値は document.title に入れて、screenshot.py の --title で受け取る。
window.addEventListener("load", () => {
  const canvas = document.createElement("canvas");
  canvas.width = 900;
  canvas.height = 600;

  const ctx = canvas.getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 900, 600);
  gradient.addColorStop(0, "#ffb347");
  gradient.addColorStop(1, "#4f7cff");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 900, 600);
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.arc(450, 300, 140, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#111";
  ctx.font = "bold 60px sans-serif";
  ctx.fillText("TEST 900x600", 250, 320);

  canvas.toBlob((blob) => {
    // character.js の関数をそのまま呼ぶ
    openIconCropper(new File([blob], "test.png", { type: "image/png" }));

    setTimeout(() => {
      const stage = document.getElementById("iconCropStage").getBoundingClientRect();
      const frame = document.querySelector(".crop-frame").getBoundingClientRect();
      const box = getCropBoxRect();

      // CSSの枠の位置と、JSが切り抜きに使う計算値が一致しているかを見比べる
      document.title = JSON.stringify({
        stage: [stage.width, stage.height],
        frameByCss: [frame.left - stage.left, frame.top - stage.top, frame.width],
        frameByJs: [box.left, box.top, box.size],
      });

      if (location.hash === "#apply") {
        document.getElementById("iconCropApply").click();
      }
    }, 600);
  }, "image/png");
});

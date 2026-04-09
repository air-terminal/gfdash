// 1. chart.js用カスタムプラグインの定義
const verticalLinePlugin = {
    id: 'verticalLinePlugin',
    // グラフ（データセット）の描画が終わった後に実行
    afterDatasetsDraw(chart, args, pluginOptions) {
        const { ctx, chartArea: { top, bottom, right, width, height }, scales: { x, y } } = chart;
        const index = chart.data.datasets[0].lineAtIndex;

        if (index !== undefined && index !== null && index > 0) {
            // インデックスからX座標を取得 (getPixelForTick は目盛りの位置を返します)
            const xPos = x.getPixelForTick(index);

            // --- 境界線の描画 ---
            ctx.save();
            ctx.beginPath();
            ctx.strokeStyle = '#ff0000';
            ctx.lineWidth = 1;
            ctx.moveTo(xPos, top);
            ctx.lineTo(xPos, bottom);
            ctx.stroke();
            ctx.restore();

            // --- 四角形（背景）の描画 ---
            ctx.save();
            ctx.fillStyle = "rgba(0, 0, 0, 0.1)";
            // xPosからグラフの右端（right）までを塗りつぶす例
            ctx.fillRect(
                xPos, 
                top, 
                right - xPos, 
                height
            );
            ctx.restore();
        }
    }
};

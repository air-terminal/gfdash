/*
    各画面専用javascript
    画面名：410raijyo_forecast.html
*/

function initFor410(){
    let initParam = {
        getMode: 'init',
        getYM: ''
    };
    sub410_postView(initParam);
}

function sub410_postView(postParam){
    // viewsへ予測データを問い合わせ
    $.ajax({
        type: "POST",
        url: location.pathname, // config_customで紐づけたURLに送信
        dataType: 'json',
        data: {
            getMode: postParam.getMode,
            getYM: postParam.getYM
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
            if (typeof NProgress != 'undefined') { NProgress.start(); }   
        },
    }).done(function (results) {
        
        // ヘッダーテキストとカレンダー初期値の設定
        $("#forecast_header").text(results.header);
        $("#calendar_initval").val(results.initYMD);

        // ▼ KPIタイルの数値をセット（カンマ区切りで表示）
        $("#kpi_landing").text(results.kpiLanding.toLocaleString());
        $("#kpi_actual").text(results.kpiActual.toLocaleString());
        $("#kpi_forecast_total").text(results.kpiForecastTotal.toLocaleString());
        $("#kpi_prev_year_same_month").text(results.kpiPrevYearSameMonth.toLocaleString());

        // ▼ 追加：AIレポートテキストを画面の要素に注入
        //$("#ai_report_forecast").text(results.reportForecast1m);
        //$("#ai_report_review").text(results.reportReview);
        // AIレポートテキストをMarkdownからHTMLに変換して画面に注入
        // ※ .text() ではなく .html() を使い、marked.parse() で変換します
        if (results.reportForecast1m) {
            $("#ai_report_forecast").html(marked.parse(results.reportForecast1m));
        }
        if (results.reportReview) {
            $("#ai_report_review").html(marked.parse(results.reportReview));
        }
        
        // --- Markdown変換後のテーブル（表）に対するデザイン調整 ---
        // marked.js が作った <table> タグに、Bootstrapの綺麗なデザインクラスを自動付与します
        $("#ai_report_forecast table, #ai_report_review table").addClass("table table-striped table-bordered table-sm").css("margin-top", "10px");
        
        
        // ▼ 追加：予測レポートの初期状態コントロール ▼
        var $forecastWrap = $('#ai_report_forecast_wrap');
        var $forecastIcon = $forecastWrap.siblings('h4').find('.gf-toggle-icon');

        if (results.hasReview) {
            // ① 振り返りがある場合 ＝ 予測レポートを「畳んだ状態」にする
            $forecastWrap.hide();
            $forecastIcon.removeClass('fa-chevron-up').addClass('fa-chevron-down');
        } else {
            // ② 振り返りがない(予測のみ)場合 ＝ 予測レポートを「展開した状態」にする
            $forecastWrap.show();
            $forecastIcon.removeClass('fa-chevron-down').addClass('fa-chevron-up');
        }
        // ▲ ここまで ▲

        // --- Chart.js 描画処理 ---
        if (typeof(Chart) !== 'undefined' && results.xLabels) {
            
            if (window.ForecastChart) {
                window.ForecastChart.destroy();
            }

            var ctx = document.getElementById("chart_forecast_canvas");
            window.ForecastChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: results.xLabels,
                    datasets: [
                        // --- 累計データ (右軸 y2 に表示) ---
                        {
                            label: "累計予測",
                            data: results.forecastCumsum,
                            // ▼ 修正：薄い紺から「半透明のパープル」に変更
                            borderColor: "rgba(155, 89, 182, 0.5)",
                            borderWidth: 2,
                            borderDash: [3, 3],
                            fill: false,
                            yAxisID: 'y2',
                            tension: 0.1,
                            pointRadius: 0,
                            order: 5
                        },
                        {
                            label: "累計実績",
                            data: results.actualCumsum,
                            // ▼ 修正：薄い緑から「半透明のオレンジ」に変更
                            borderColor: "rgba(230, 126, 34, 0.6)",
                            borderWidth: 2,
                            fill: false,
                            yAxisID: 'y2',
                            tension: 0.1,
                            pointRadius: 0,
                            order: 6
                        },
                        // --- 日別データ (左軸 y1 に表示) ---
                        {
                            label: "実績来場者数",
                            data: results.actualData,
                            borderColor: "rgba(38, 185, 154, 1)",
                            backgroundColor: "rgba(38, 185, 154, 1)",
                            borderWidth: 3,
                            fill: false,
                            yAxisID: 'y1',
                            tension: 0.1,
                            pointRadius: 2,
                            order: 1
                        },
                        {
                            label: "AI予測値",
                            data: results.predictYhat,
                            borderColor: "rgba(3, 88, 106, 1)",
                            borderDash: [5, 5],
                            borderWidth: 3,
                            fill: false,
                            yAxisID: 'y1',
                            tension: 0.1,
                            pointRadius: 0,
                            order: 2
                        },
                        {
                            label: "予測下限",
                            data: results.predictLower,
                            borderColor: "rgba(3, 88, 106, 0.05)",
                            borderWidth: 0,
                            pointRadius: 0,
                            fill: false,
                            yAxisID: 'y1',
                            tension: 0.1,
                            order: 3
                        },
                        {
                            label: "予測上限",
                            data: results.predictUpper,
                            borderColor: "rgba(3, 88, 106, 0.05)",
                            borderWidth: 0,
                            pointRadius: 0,
                            fill: "-1", 
                            backgroundColor: "rgba(3, 88, 106, 0.12)",
                            yAxisID: 'y1',
                            tension: 0.1,
                            order: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: {
                            grid: { color: "rgba(0, 0, 0, 0.05)" },
                            ticks: { font: { size: 11 },
                                // コールバック関数を使ってラベルの色を動的に変更
                                color: function(context) {
                                    return com_setChartLabelColor(context);
                                }
                            }
                        },
                        y1: {
                            type: 'linear',
                            position: 'left',
                            title: { display: true, text: '日別 来場者数 (人)', font: { weight: 'bold' } },
                            grid: { color: "rgba(0, 0, 0, 0.05)" }
                        },
                        y2: {
                            type: 'linear',
                            position: 'right',
                            title: { display: true, text: '累計 来場者数 (人)', font: { weight: 'bold' } },
                            grid: { drawOnChartArea: false }, // 右軸のグリッド線は消す(左軸と被って見にくくなるため)
                            min: 0 // 累計は必ず0スタート
                        }
                    }
                }
            });
        }

        // --- カレンダー(Datepicker)の表示制御 ---
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        var month = (newDate.getMonth() + 1).toString();

        if (postParam.getMode === 'init'){
            $.fn.datepicker.defaults.language = 'ja';
            $.fn.datepicker.defaults.minViewMode = 1;
            $.fn.datepicker.defaults.maxViewMode = 2;
            $.fn.datepicker.defaults.format = 'yyyy年MM';
            $.fn.datepicker.defaults.autoclose = true;
        
            sub410_init_datepicker();
        }
        
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年' + month + '月');
        $("#calendar_saveval").val($("#gf_calendar").val());

    }).fail(function (jqXHR, textStatus, errorThrown) {
        console.log("予測データの取得に失敗しました", errorThrown);
    });

    if (typeof NProgress != 'undefined') { NProgress.done(); }   
    return false;
}

// Datepickerのイベントバインド（101画面を踏襲）
function sub410_init_datepicker() {
    if (typeof($.fn.datepicker) === 'undefined') return;
    
    $('.input-group.date').datepicker()
    .on('changeDate', function(obj) {
        $("#calendar_saveval").val($("#gf_calendar").val());
        let param = {
            getMode: 'get',
            getYM: com_convStrDateTime(obj.date) + ' 00:00:00'
        };
        sub410_postView(param);
    })
    .on('hide', function(obj){
        $("#gf_calendar").val($("#calendar_saveval").val());
    });
}

// 前月ボタン
function btnPrevMonth(){
    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 1);
    executeMonthChange(newDate);
}

// 翌月ボタン
function btnNextMonth(){
    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 1);
    executeMonthChange(newDate);
}

function executeMonthChange(targetDate) {
    let param = {
        getMode: 'get',
        getYM: com_convStrDateTime(targetDate) + ' 00:00:00'
    };
    $('.input-group.date').datepicker('update', targetDate);
    sub410_postView(param);
}

// ページロード時の初期化
$(document).ready(function() {
    initFor410();
});
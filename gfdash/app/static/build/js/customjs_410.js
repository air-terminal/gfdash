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
        // iPad 縦向き用の小型の表にも同じ数値を入れる
        $(".gf_kpi_landing").text(results.kpiLanding.toLocaleString());
        $(".gf_kpi_actual").text(results.kpiActual.toLocaleString());
        $(".gf_kpi_forecast_total").text(results.kpiForecastTotal.toLocaleString());
        $(".gf_kpi_prev_year_same_month").text(results.kpiPrevYearSameMonth.toLocaleString());

        // ▼ 追加：AIレポートテキストを画面の要素に注入
        //$("#ai_report_forecast").text(results.reportForecast1m);
        //$("#ai_report_review").text(results.reportReview);
        // AIレポートテキストをMarkdownからHTMLに変換して画面に注入
        // ※ .text() ではなく .html() を使い、marked.parse() で変換します
        if (results.reportForecast1m) {
            $("#ai_report_forecast").html(marked.parse(results.reportForecast1m));
        }
        // 運営者の所見。レポートより先に描く（何を織り込んだかを先に示す）
        sub410_renderRemarks(results.remarks);

        if (results.reportReview) {
            $("#ai_report_review").html(marked.parse(results.reportReview));
        }
        
        // --- Markdown変換後のテーブル（表）に対するデザイン調整 ---
        // marked.js が作った <table> タグに、Bootstrapの綺麗なデザインクラスを自動付与します
        $("#ai_report_forecast table, #ai_report_review table").addClass("table table-striped table-bordered table-sm").css("margin-top", "10px");
        
        
        // レビューがある月はレビューを、まだ無い月は先行予測を最初に開く
        sub410_showReportTab(results.hasReview ? 'review' : 'forecast');

        // モデルごとの見比べ（github issue #28）。今の月を覚え、履歴の選択を描く。
        // 機能を切っている環境（既定の off）では、見出しのボタンごと出さない。
        // 初めに開くか（expanded）は、画面を開いた最初の読み込みでだけ当てる
        g410Ym = results.initYMD;
        g410Runs = results.reportRuns || {};
        g410Compare = results.modelCompare === 'collapsed' || results.modelCompare === 'expanded';
        $('#compare_ctl_410').toggle(g410Compare);
        if (!g410CompareInit) {
            g410CompareInit = true;
            sub410_setCompareOpen(results.modelCompare === 'expanded');
        }
        sub410_renderRuns('forecast_1m');
        sub410_renderRuns('review');
        sub410_applyPending();

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
                            // 全日を出す。間引くと、曜日の並びが追えなくなる。
                            // 幅が足りるように「日」と「曜日」の2段にして、斜めにしない
                            ticks: { font: { size: 11 },
                                autoSkip: false,
                                maxRotation: 0,
                                callback: function(value) {
                                    return sub410_splitDayLabel(this.getLabelForValue(value));
                                },
                                // コールバック関数を使ってラベルの色を動的に変更
                                color: function(context) {
                                    var label = context.tick.label;
                                    if (Array.isArray(label)) { label = label.join(''); }
                                    return com_setChartLabelColor({ tick: { label: label } });
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

/* ============================================================
   運営者の所見（読み取り専用）

   グラフとレポートが何を織り込んでいるのかを示す。数値だけを見せると、
   補正が入っていることに気づけない。入力は 480 で行う。
   ============================================================ */

function sub410_renderRemarks(pRemarks) {
    var remarks = pRemarks || [];

    // 所見の無い月では枠ごと出さない。空の見出しだけが残ると場所を取る
    if (remarks.length === 0) {
        $('#remark_panel_row').hide();
        return;
    }
    $('#remark_panel_row').show();

    // 畳んでいても、所見があることと、予測に反映されているかは見出しで分かるようにする
    var nConfirmed = remarks.filter(function(r) { return r.confirmed; }).length;
    var summary = remarks.length + '件';
    summary += (nConfirmed === remarks.length)
        ? '<span class="gf_rmk_state gf_rmk_state_on">確認済み</span>'
        : '<span class="gf_rmk_state gf_rmk_state_off">未確認あり</span>';
    $('#remark_summary').html('<small style="font-size: 12px; font-weight: normal; margin-left: 6px;">' + summary + '</small>');

    var html = '';
    var tabs = '';

    for (var i = 0; i < remarks.length; i++) {
        var r = remarks[i];

        // 区分の名前はタブに出す。本文の側には確認済みかどうかだけを出す
        tabs += '<li data-cls="' + sub410_escape(r.cls) + '">'
              + '<a href="#" onclick="return sub410_showRemarkTab(\'' + sub410_escape(r.cls) + '\')">'
              + sub410_escape(r.label) + '</a></li>';

        html += '<div class="gf_remark_pane_410" data-cls="' + sub410_escape(r.cls) + '" style="margin-bottom: 14px;">';
        html += '<div style="margin-bottom: 4px;">'
              + (r.confirmed
                 ? '<span class="gf_rmk_state gf_rmk_state_on">確認済み</span>'
                 : '<span class="gf_rmk_state gf_rmk_state_off">未確認 — 予測とレポートには反映されていません</span>')
              + '</div>';

        html += '<div style="font-size:13px; color:#4B5F71; white-space:pre-wrap;'
              + ' background-color:#FAFBFC; border:1px solid #E6E9ED; border-radius:3px;'
              + ' padding:8px 10px;">' + sub410_escape(r.text) + '</div>';

        if (r.events && r.events.length) {
            html += '<ul style="margin:6px 0 0 0; padding-left:18px; font-size:12px; color:#4B5F71;">';
            for (var j = 0; j < r.events.length; j++) {
                var e = r.events[j];
                var uses = [];
                if (e.use_for_forecast) { uses.push('予測'); }
                if (e.use_for_report) { uses.push('レポート'); }

                html += '<li>' + sub410_escape(e.name)
                      + ' <span class="text-muted">（' + sub410_escape(e.type_name) + '）</span> '
                      + sub410_escape(e.period);
                if (e.percent !== null && e.percent !== undefined) {
                    html += ' <b>' + (e.percent > 0 ? '+' : '') + e.percent + '%</b>';
                }
                if (uses.length) {
                    html += ' <span class="text-muted">[' + uses.join(' / ') + ']</span>';
                }
                if (e.rationale) {
                    html += '<br><span class="text-muted">' + sub410_escape(e.rationale) + '</span>';
                }
                html += '</li>';
            }
            html += '</ul>';
        }

        html += '</div>';
    }

    $('#remark_tabs_410').html(tabs);
    $('#remark_view').html(html);

    // レポートのタブと同じく、レビューがあればレビューを最初に開く
    var hasReview = remarks.some(function(r) { return r.cls === 'review'; });
    sub410_showRemarkTab(hasReview ? 'review' : remarks[0].cls);
}

// 月次分析レポートのタブ切り替え（'forecast' / 'review'）
function sub410_showReportTab(pTab) {
    $('#report_tabs_410 > li').each(function() {
        $(this).toggleClass('active', $(this).data('tab') === pTab);
    });
    $('#ai_report_forecast_wrap').toggle(pTab === 'forecast');
    $('#ai_report_review_wrap').toggle(pTab === 'review');
    return false;
}

// 運営者の所見のタブ切り替え（所見の区分 'forecast' / 'review'）
function sub410_showRemarkTab(pCls) {
    $('#remark_tabs_410 > li').each(function() {
        $(this).toggleClass('active', $(this).data('cls') === pCls);
    });
    $('#remark_view > .gf_remark_pane_410').each(function() {
        $(this).toggle($(this).data('cls') === pCls);
    });
    return false;
}

// グラフの見方をダイアログで出す
function sub410_showChartHelp() {
    Swal.fire({
        title: 'グラフの見方',
        html: $('#chart_help_410').html(),
        width: 640,
        confirmButtonText: '閉じる'
    });
}

// 日付ラベル「10/01㈬」を、2段の「01」「㈬」に分ける。形が違えばそのまま返す
function sub410_splitDayLabel(pLabel) {
    var m = /^\d{2}\/(\d{2})(.*)$/.exec(pLabel || '');
    return m ? [m[1], m[2]] : pLabel;
}

function sub410_escape(pText) {
    return $('<div>').text(pText === undefined || pText === null ? '' : pText).html();
}


/* ============================================================
   月次レポートをモデルごとに見比べる（github issue #28）

   同じ月・同じ種類のレポートの履歴（tz312）を、「モデル × プロンプトの版」で分けて
   選べるようにする。プロンプトの版が違うと結果も違うので、版でも分ける。
   選んだ組の中は「前」「次」で古い実行・新しい実行に移れる。所見を書き換えて
   再実行した前後を、同じモデル・同じ版で見比べるため。
   読むだけで、採用中のレポート（tz302）は変わらない。
   ============================================================ */

var g410Ym = '';
var g410Runs = {};
// 機能が有効か（.env の REPORT_MODEL_COMPARE）と、見比べの欄を開いているか。
// 開いた状態は月を移っても保つが、画面を開き直すと設定の初めの状態に戻る
var g410Compare = false;
var g410CompareOpen = false;
var g410CompareInit = false;

// 他の月を探すボタン。見比べの欄の右端に置く
var G410_SEARCH_BTN = '<button type="button" class="btn btn-default btn-xs gf_runs_search_btn"'
                    + ' onclick="sub410_openSearch()" title="モデル・プロンプトの版でレポートを探す">'
                    + '<i class="fa fa-search"></i> 他の月を探す</button>';
// 検索の結果から月を移るとき、読み込みのあとで開く実行
var g410Pending = null;
// 種類ごとに、いま表示している実行の番号（null は採用中のレポート）
var g410Shown = {};

var G410_RUN_TARGET = { forecast_1m: '#ai_report_forecast', review: '#ai_report_review' };

function sub410_groupKey(pRun) {
    return pRun.model + ' | ' + pRun.prompt;
}

// 組ごとの実行（古い順）。組の並びは、新しい実行のある組から
function sub410_runGroups(pCls) {
    var runs = (g410Runs[pCls] || {}).runs || [];
    var groups = {};
    var order = [];
    for (var i = 0; i < runs.length; i++) {
        var key = sub410_groupKey(runs[i]);
        if (!groups[key]) { groups[key] = []; order.push(key); }
        groups[key].push(runs[i]);
    }
    order.sort(function(a, b) {
        var la = groups[a][groups[a].length - 1].executedAt;
        var lb = groups[b][groups[b].length - 1].executedAt;
        return la < lb ? 1 : (la > lb ? -1 : 0);
    });
    return { groups: groups, order: order };
}

function sub410_renderRuns(pCls) {
    var $box = $('#report_runs_' + pCls);
    var info = g410Runs[pCls] || {};
    var runs = info.runs || [];
    g410Shown[pCls] = info.current || null;

    if (!g410Compare || !g410CompareOpen) { $box.empty().hide(); return; }

    // 履歴が1本も無い月（履歴を残す前に作ったレポートなど）は、無いことと、他の月を探す道を出す
    if (runs.length === 0) {
        $box.html('<span class="gf_runs_info">この月のレポートの履歴はありません</span>' + G410_SEARCH_BTN).show();
        return;
    }

    var g = sub410_runGroups(pCls);
    var html = '<select class="gf_runs_select">';
    if (!info.current) {
        // 採用中のレポートが履歴のどれとも一致しない（履歴を残す前のものなど）
        html += '<option value="" selected>採用中のレポート（履歴なし）</option>';
    }
    for (var i = 0; i < g.order.length; i++) {
        var list = g.groups[g.order[i]];
        var last = list[list.length - 1];
        var hasCurrent = list.some(function(r) { return r.runId === info.current; });
        html += '<option value="' + sub410_escape(g.order[i]) + '"' + (hasCurrent ? ' selected' : '') + '>'
              + sub410_escape(last.model + ' · ' + last.prompt) + '（' + list.length + '回'
              + (hasCurrent ? '・採用中' : '') + '）</option>';
    }
    html += '</select>'
          + '<div class="btn-group">'
          + '<button type="button" class="btn btn-default btn-xs gf_runs_prev"><i class="fa fa-chevron-left"></i> 前</button>'
          + '<button type="button" class="btn btn-default btn-xs gf_runs_next">次 <i class="fa fa-chevron-right"></i></button>'
          + '</div>'
          + '<span class="gf_runs_info"></span>'
          + G410_SEARCH_BTN;
    $box.html(html).show();

    $box.find('.gf_runs_select').on('change', function() { sub410_selectGroup(pCls, $(this).val()); });
    $box.find('.gf_runs_prev').on('click', function() { sub410_stepRun(pCls, -1); });
    $box.find('.gf_runs_next').on('click', function() { sub410_stepRun(pCls, 1); });
    sub410_syncRunBar(pCls);
}

// いま表示している実行の位置に合わせて、前後のボタンと説明を直す
function sub410_syncRunBar(pCls) {
    var $box = $('#report_runs_' + pCls);
    var shown = g410Shown[pCls];
    var current = (g410Runs[pCls] || {}).current;
    var key = $box.find('.gf_runs_select').val();
    var list = key ? (sub410_runGroups(pCls).groups[key] || []) : [];
    var idx = -1;
    for (var i = 0; i < list.length; i++) { if (list[i].runId === shown) { idx = i; } }

    $box.find('.gf_runs_prev').prop('disabled', idx <= 0);
    $box.find('.gf_runs_next').prop('disabled', idx < 0 || idx >= list.length - 1);

    if (idx < 0) {
        $box.find('.gf_runs_info').text('');
        return;
    }
    var r = list[idx];
    $box.find('.gf_runs_info').html(
        sub410_escape(r.executedAt) + ' 実行（' + (idx + 1) + ' / ' + list.length + '）'
        + (r.runId === current ? ' <span class="gf_runs_current">採用中</span>' : ''));
}

function sub410_selectGroup(pCls, pKey) {
    if (!pKey) {
        // 採用中のレポート（履歴なし）に戻す。今の月を読み直す
        executeMonthChange(new Date(g410Ym));
        return;
    }
    var list = sub410_runGroups(pCls).groups[pKey] || [];
    if (list.length) { sub410_loadRun(pCls, list[list.length - 1].runId); }
}

function sub410_stepRun(pCls, pStep) {
    var $box = $('#report_runs_' + pCls);
    var list = sub410_runGroups(pCls).groups[$box.find('.gf_runs_select').val()] || [];
    for (var i = 0; i < list.length; i++) {
        if (list[i].runId === g410Shown[pCls]) {
            var next = list[i + pStep];
            if (next) { sub410_loadRun(pCls, next.runId); }
            return;
        }
    }
}

// 見比べ・検索の問い合わせ（読むだけ）
function sub410_post(pData, pDone) {
    $.ajax({
        type: 'POST',
        url: location.pathname,
        dataType: 'json',
        data: pData,
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    }).done(pDone);
}

function sub410_loadRun(pCls, pRunId) {
    sub410_post({ getMode: 'report_run', getYM: g410Ym, reportCls: pCls, runId: pRunId }, function(res) {
        if (!res.success) { return; }
        var $target = $(G410_RUN_TARGET[pCls]);
        $target.html(marked.parse(res.reportText));
        $target.find('table').addClass("table table-striped table-bordered table-sm").css("margin-top", "10px");
        g410Shown[pCls] = pRunId;
        sub410_syncRunBar(pCls);
    });
}

// 見比べの欄を開く／畳む。畳むときは、採用中のレポートの表示に戻す
function sub410_toggleCompare() {
    sub410_setCompareOpen(!g410CompareOpen);

    var changed = false;
    $.each(G410_RUN_TARGET, function(cls) {
        if (g410Shown[cls] !== ((g410Runs[cls] || {}).current || null)) { changed = true; }
    });
    if (!g410CompareOpen && changed) {
        executeMonthChange(new Date(g410Ym));
        return;
    }
    sub410_renderRuns('forecast_1m');
    sub410_renderRuns('review');
}

// 開いているかと、見出しのボタンの向きを合わせる（欄を描くのは呼び出し側）
function sub410_setCompareOpen(pOpen) {
    g410CompareOpen = pOpen;
    $('#btn_compare_410 i').toggleClass('fa-chevron-down', !pOpen).toggleClass('fa-chevron-up', pOpen);
    $('#btn_compare_410').toggleClass('active', pOpen);
}

/* ------------------------------------------------------------
   レポートを探す（検索ダイアログ）

   モデル・プロンプトの版（どちらか、または両方）で、月 × 種類の行を新しい月から出す。
   行を選ぶと、その月に移り、条件に合う一番新しい実行を開く。そこから先は、
   レポートの上の選択と「前」「次」で見比べる
   ------------------------------------------------------------ */

var g410SearchRows = [];

function sub410_openSearch() {
    sub410_post({ getMode: 'report_search_opts' }, function(opts) {
        if (!opts.success) { return; }
        var sel = function(pId, pList) {
            var h = '<select id="' + pId + '" class="form-control input-sm"><option value="">（指定しない）</option>';
            for (var i = 0; i < pList.length; i++) {
                h += '<option value="' + sub410_escape(pList[i]) + '">' + sub410_escape(pList[i]) + '</option>';
            }
            return h + '</select>';
        };
        var html = '<div class="gf_runs_search">'
                 + '<div class="gf_runs_search_form">'
                 + '<label>プロンプトの版' + sel('s410_prompt', opts.prompts) + '</label>'
                 + '<label>モデル' + sel('s410_model', opts.models) + '</label>'
                 + '</div>'
                 + '<div class="gf_runs_search_result" id="s410_result"></div>'
                 + '</div>';
        Swal.fire({
            title: 'レポートを探す',
            html: html,
            width: 760,
            confirmButtonText: '閉じる',
            didOpen: function() {
                $('#s410_prompt, #s410_model').on('change', sub410_runSearch);
                sub410_runSearch();
            }
        });
    });
}

function sub410_runSearch() {
    var model = $('#s410_model').val();
    var prompt = $('#s410_prompt').val();
    var $res = $('#s410_result');
    if (!model && !prompt) {
        $res.html('<p class="gf_runs_search_note">プロンプトの版かモデルを選んでください（両方でも探せます）</p>');
        return;
    }
    sub410_post({ getMode: 'report_search', model: model, prompt: prompt }, function(res) {
        if (!res.success) { return; }
        // 選び直している間に古い結果が後から届くことがある。今の選択の結果だけを描く
        if ($('#s410_model').val() !== model || $('#s410_prompt').val() !== prompt) { return; }
        g410SearchRows = res.rows;
        if (res.rows.length === 0) {
            $res.html('<p class="gf_runs_search_note">該当するレポートはありません</p>');
            return;
        }
        var html = '<p class="gf_runs_search_note">' + res.rows.length + '件。行を選ぶと、その月のレポートを開きます</p>'
                 + '<table class="table table-condensed table-hover gf_runs_search_table">'
                 + '<thead><tr><th>月</th><th>種類</th><th>モデル · プロンプトの版</th><th>最新の実行</th></tr></thead><tbody>';
        for (var i = 0; i < res.rows.length; i++) {
            var r = res.rows[i];
            // 一番新しい組だけを出し、残りは「他 N組」にまとめる。片方の条件だけで探すと、
            // 1つの月に10組を超えることがあり、一覧が読めなくなるため。
            // 行を選ぶと開くのもこの組。残りの組は、マウスを乗せると一覧で出る
            var label = function(g) { return g.model + ' · ' + g.prompt + '（' + g.count + '回）'; };
            var groups = sub410_escape(label(r.groups[0]));
            if (r.groups.length > 1) {
                groups += ' <span class="gf_runs_more" title="'
                        + sub410_escape(r.groups.slice(1).map(label).join('\n')) + '">他 '
                        + (r.groups.length - 1) + '組</span>';
            }
            html += '<tr data-idx="' + i + '">'
                  + '<td class="gf_nowrap">' + sub410_escape(r.ym) + '</td>'
                  + '<td class="gf_nowrap">' + sub410_escape(r.clsName) + '</td>'
                  + '<td>' + groups + '<span class="gf_runs_total">全' + r.total + '回</span></td>'
                  + '<td class="gf_nowrap">' + sub410_escape(r.latestAt) + '</td>'
                  + '</tr>';
        }
        html += '</tbody></table>';
        $res.html(html);
        $res.find('tbody tr').on('click', function() {
            sub410_openSearchRow(g410SearchRows[$(this).data('idx')]);
        });
    });
}

// 検索の行を開く。月を移り、読み込みのあとで種類のタブと実行を選ぶ（sub410_applyPending）
function sub410_openSearchRow(pRow) {
    if (!pRow) { return; }
    Swal.close();
    g410Pending = { cls: pRow.cls, key: pRow.model + ' | ' + pRow.prompt, runId: pRow.runId };
    executeMonthChange(new Date(pRow.getYM));
}

function sub410_applyPending() {
    var p = g410Pending;
    g410Pending = null;
    if (!p || !g410Compare || !g410CompareOpen) { return; }
    sub410_showReportTab(p.cls === 'review' ? 'review' : 'forecast');
    $('#report_runs_' + p.cls + ' .gf_runs_select').val(p.key);
    sub410_loadRun(p.cls, p.runId);
}

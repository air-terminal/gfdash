/*
    各画面専用javascript
    415forecast_hikaku.html

    予測の実行履歴を2つ選んで、日別の予測値を重ねて比べる。
    所見による補正を入れたとき、その前後で何がどれだけ変わったかを
    確認するための画面。
*/

// 選んだ実行。先に選んだものを A、後を B として扱う
let sub415_picked = [];

$(document).ready(function() {
    sub415_loadRuns();
});

function btnReload() {
    sub415_loadRuns();
}

function btnCompare() {
    if (sub415_picked.length !== 2) { return; }
    sub415_compare(sub415_picked[0], sub415_picked[1]);
}

function sub415_loadRuns() {
    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: { getMode: 'list' },
        beforeSend: function(xhr) {
            if (typeof com_csrftoken !== 'undefined') {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
            if (typeof NProgress != 'undefined') { NProgress.start(); }
        }
    }).done(function(res) {
        if (!res.compare_success) {
            Swal.fire('エラー', res.err_message || '一覧を取得できませんでした。', 'error');
            return;
        }
        sub415_renderRuns(res.runs);
    }).fail(function() {
        Swal.fire('エラー', '通信に失敗しました。', 'error');
    }).always(function() {
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

function sub415_renderRuns(pRuns) {
    // 一覧を入れ替えるので選択状態は持ち越さない。
    // 消えた実行が選ばれたままになると、比較できない組み合わせが残る
    sub415_picked = [];
    $('#result_area').hide();

    if (!pRuns || pRuns.length === 0) {
        $('#run_tbody').html(
            '<tr><td colspan="10" class="text-muted">'
            + '予測の実行履歴がありません。AIバッチ実行画面(490)から予測を実行してください。'
            + '</td></tr>');
        sub415_updatePickState();
        return;
    }

    var html = '';
    for (var i = 0; i < pRuns.length; i++) {
        var r = pRuns[i];
        var hasData = r.day_count > 0;

        html += '<tr class="' + (hasData ? '' : 'gf_run_nodata') + '" data-run="' + r.run_id + '">';
        html += '<td>' + (hasData
            ? '<input type="checkbox" class="sub415_pick" value="' + r.run_id + '">'
            : '<span class="text-muted">—</span>') + '</td>';
        html += '<td>' + r.run_id + '</td>';
        html += '<td>' + sub415_escape(r.executed_at) + '</td>';
        html += '<td>' + sub415_statusLabel(r.status) + '</td>';
        html += '<td class="text-right">' + sub415_orDash(r.periods) + '</td>';
        html += '<td class="text-right">' + r.day_count + '</td>';
        html += '<td>' + sub415_boolLabel(r.holiday2_enabled) + '</td>';
        html += '<td class="text-right">' + sub415_orDash(r.closure_sample_count) + '</td>';
        html += '<td>' + (r.has_remark ? 'あり' : '—') + '</td>';
        html += '<td class="gf_run_note">' + sub415_escape(r.note) + '</td>';
        html += '</tr>';
    }

    $('#run_tbody').html(html);

    $('#run_tbody').off('change', '.sub415_pick').on('change', '.sub415_pick', function() {
        sub415_onPick($(this));
    });

    sub415_updatePickState();
}

function sub415_onPick($pCheckbox) {
    var runId = parseInt($pCheckbox.val(), 10);

    if ($pCheckbox.prop('checked')) {
        // 3つ目を選ばせない。古い選択を外すより、選べないことを伝えるほうが
        // 「なぜ勝手に外れたのか」と迷わせずに済む
        if (sub415_picked.length >= 2) {
            $pCheckbox.prop('checked', false);
            Swal.fire({
                title: '選択は2つまで',
                text: 'どちらかの選択を外してから選んでください。',
                icon: 'info',
                customClass: { popup: 'gf_swal_415' }
            });
            return;
        }
        sub415_picked.push(runId);
    } else {
        sub415_picked = sub415_picked.filter(function(id) { return id !== runId; });
    }

    sub415_updatePickState();
}

function sub415_updatePickState() {
    $('#run_tbody tr').removeClass('gf_run_picked');
    $('#run_tbody tr').find('.sub415_badge').remove();

    for (var i = 0; i < sub415_picked.length; i++) {
        var $tr = $('#run_tbody tr[data-run="' + sub415_picked[i] + '"]');
        $tr.addClass('gf_run_picked');
        $tr.children('td').eq(1).prepend(
            '<span class="gf_run_badge sub415_badge gf_run_badge_'
            + (i === 0 ? 'a' : 'b') + '" style="margin-right:4px;">'
            + (i === 0 ? 'A' : 'B') + '</span>');
    }

    $('#btn_compare').prop('disabled', sub415_picked.length !== 2);

    var label = '';
    if (sub415_picked.length === 0) {
        label = '比較する実行を2つ選んでください。';
    } else if (sub415_picked.length === 1) {
        label = 'あと1つ選んでください。';
    } else {
        label = 'A: run #' + sub415_picked[0] + ' / B: run #' + sub415_picked[1];
    }
    $('#pick_label').text(label);
}

function sub415_compare(pRunA, pRunB) {
    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: { getMode: 'compare', runA: pRunA, runB: pRunB },
        beforeSend: function(xhr) {
            if (typeof com_csrftoken !== 'undefined') {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
            if (typeof NProgress != 'undefined') { NProgress.start(); }
        }
    }).done(function(res) {
        if (!res.compare_success) {
            Swal.fire('エラー', res.err_message || '比較できませんでした。', 'error');
            return;
        }
        sub415_renderResult(res);
    }).fail(function() {
        Swal.fire('エラー', '通信に失敗しました。', 'error');
    }).always(function() {
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

function sub415_renderResult(pRes) {
    $('#result_area').show();
    $('#compare_header').html(
        '<span class="gf_run_head_title">比較結果</span>'
        + sub415_runHeadHtml(pRes.runA, 'a')
        + '<span class="gf_run_head_sep">/</span>'
        + sub415_runHeadHtml(pRes.runB, 'b'));

    sub415_renderSummary(pRes);
    sub415_renderChart(pRes);
    sub415_renderDetail(pRes.detail);
}

function sub415_runHeadHtml(pRun, pKey) {
    // A/B は表とグラフの線色に合わせたバッジで示す。文字だけだと、
    // グラフのどちらの線の話なのかを読み手が対応付け直すことになる
    return '<span class="gf_run_badge gf_run_badge_' + pKey + '" style="margin-right:4px;">'
         + pKey.toUpperCase() + '</span>'
         + 'run #' + pRun.run_id
         + ' <span class="gf_run_head_date">(実行日: '
         + sub415_escape(pRun.executed_at) + ')</span>';
}

function sub415_renderSummary(pRes) {
    var s = pRes.summary;
    var html = '';

    // 差がまったく無い場合は、それ自体が結論なので最初に言う
    if (s.identical) {
        html += '<p style="margin-bottom:8px;"><b>2つの実行で予測値は一致しています。</b>'
             + ' 条件が同じであれば予測は同じ結果になります。</p>';
    }

    html += '<table style="width:100%; font-size:13px;"><tr>';
    html += '<td>対象日数: <b>' + s.days + '</b> 日（両方に値がある日: ' + s.bothDays + ' 日）</td>';
    html += '<td>合計の差: ' + sub415_diffHtml(s.sumDiff)
         + (s.sumRate === null ? '' : '（' + sub415_signed(s.sumRate) + '%）') + '</td>';
    html += '<td>1日あたりの最大差: <b>' + s.maxAbsDiff + '</b></td>';
    html += '</tr></table>';

    html += sub415_condDiffHtml(pRes.runA, pRes.runB);

    $('#summary_box').html(html);
}

function sub415_condDiffHtml(pA, pB) {
    // 条件の違いを並べる。差が出たとき、その原因の候補を指すため
    var rows = [];
    function add(pName, pValA, pValB) {
        if (String(pValA) !== String(pValB)) {
            rows.push('<li>' + pName + ': A=' + pValA + ' / B=' + pValB + '</li>');
        }
    }

    add('予測日数', sub415_orDash(pA.periods), sub415_orDash(pB.periods));
    add('第2休日', sub415_boolLabel(pA.holiday2_enabled), sub415_boolLabel(pB.holiday2_enabled));
    add('休業補正の実績日数', sub415_orDash(pA.closure_sample_count), sub415_orDash(pB.closure_sample_count));
    add('所見', pA.has_remark ? 'あり' : 'なし', pB.has_remark ? 'あり' : 'なし');
    add('スクリプト版', pA.script_version || '—', pB.script_version || '—');

    if (rows.length === 0) {
        return '<p style="margin:8px 0 0 0; color:#888;">記録された実行条件に違いはありません。</p>';
    }
    return '<p style="margin:8px 0 2px 0;"><b>実行条件の違い</b></p>'
         + '<ul style="margin:0; padding-left:18px;">' + rows.join('') + '</ul>';
}

function sub415_renderChart(pRes) {
    if (typeof(Chart) === 'undefined') { return; }

    if (window.CompareChart) {
        window.CompareChart.destroy();
    }

    var ctx = document.getElementById('chart_compare_canvas');
    window.CompareChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: pRes.xLabels,
            datasets: [
                // 上下限は帯として先に描く。線より後ろに置かないと中央値が隠れる
                {
                    label: 'A 上限', data: pRes.upperA,
                    borderColor: 'rgba(90, 115, 142, 0.25)', borderWidth: 1,
                    pointRadius: 0, fill: '+1',
                    backgroundColor: 'rgba(90, 115, 142, 0.08)', order: 9
                },
                {
                    label: 'A 下限', data: pRes.lowerA,
                    borderColor: 'rgba(90, 115, 142, 0.25)', borderWidth: 1,
                    pointRadius: 0, fill: false, order: 9
                },
                {
                    label: 'B 上限', data: pRes.upperB,
                    borderColor: 'rgba(230, 126, 34, 0.25)', borderWidth: 1,
                    pointRadius: 0, fill: '+1',
                    backgroundColor: 'rgba(230, 126, 34, 0.08)', order: 8
                },
                {
                    label: 'B 下限', data: pRes.lowerB,
                    borderColor: 'rgba(230, 126, 34, 0.25)', borderWidth: 1,
                    pointRadius: 0, fill: false, order: 8
                },
                {
                    label: 'A 予測値 (run #' + pRes.runA.run_id + ')', data: pRes.yhatA,
                    borderColor: 'rgba(90, 115, 142, 1)', backgroundColor: 'rgba(90, 115, 142, 1)',
                    borderWidth: 3, fill: false, tension: 0.1, pointRadius: 2, order: 1
                },
                {
                    label: 'B 予測値 (run #' + pRes.runB.run_id + ')', data: pRes.yhatB,
                    borderColor: 'rgba(230, 126, 34, 1)', backgroundColor: 'rgba(230, 126, 34, 1)',
                    borderWidth: 3, borderDash: [5, 5], fill: false, tension: 0.1,
                    pointRadius: 2, order: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    // 上下限の4項目まで凡例に出すと読みにくい。中央値だけ出す
                    labels: {
                        filter: function(item) { return item.text.indexOf('予測値') >= 0; }
                    }
                }
            },
            scales: {
                y: { beginAtZero: false, title: { display: true, text: '予測来場者数' } }
            }
        }
    });
}

function sub415_renderDetail(pDetail) {
    var html = '';

    for (var i = 0; i < pDetail.length; i++) {
        var d = pDetail[i];
        html += '<tr>';
        html += '<td>' + sub415_escape(d.day) + '</td>';
        html += '<td class="text-right">' + sub415_orDash(d.a) + '</td>';
        html += '<td class="text-right">' + sub415_orDash(d.b) + '</td>';
        html += '<td class="text-right">' + (d.diff === null ? '—' : sub415_diffHtml(d.diff)) + '</td>';
        html += '<td class="text-right">'
             + (d.rate === null ? '—' : sub415_diffHtml(d.rate, '%')) + '</td>';
        html += '</tr>';
    }

    $('#detail_tbody').html(html);
}

function sub415_diffHtml(pValue, pUnit) {
    var unit = pUnit || '';
    var cls = 'gf_diff_zero';
    if (pValue > 0)      { cls = 'gf_diff_plus'; }
    else if (pValue < 0) { cls = 'gf_diff_minus'; }
    return '<span class="' + cls + '"><b>' + sub415_signed(pValue) + unit + '</b></span>';
}

function sub415_signed(pValue) {
    return (pValue > 0 ? '+' : '') + pValue;
}

function sub415_statusLabel(pStatus) {
    if (pStatus === 'done')    { return '完了'; }
    if (pStatus === 'failed')  { return '<span style="color:#C0392B;">失敗</span>'; }
    if (pStatus === 'running') { return '<span style="color:#E67E22;">実行中</span>'; }
    return sub415_escape(pStatus);
}

function sub415_boolLabel(pValue) {
    if (pValue === true)  { return '有効'; }
    if (pValue === false) { return '無効'; }
    return '—';
}

function sub415_orDash(pValue) {
    return (pValue === null || pValue === undefined || pValue === '') ? '—' : pValue;
}

function sub415_escape(pText) {
    return $('<div>').text(pText === undefined || pText === null ? '' : pText).html();
}

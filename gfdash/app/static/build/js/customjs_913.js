/*
    画面名：913holiday_calendar.html
*/

let sub913_year = 0;
let sub913_month = 0;
let sub913_days = [];

const SUB913_SLOT_NAMES = { morning: '朝', afternoon: '昼', night: '夜' };

$(document).ready(function() {
    sub913_year = gf_913_init.year;
    sub913_month = gf_913_init.month;
    sub913_load();
});

function sub913_move(pDiff) {
    sub913_month += pDiff;
    if (sub913_month < 1)  { sub913_month = 12; sub913_year -= 1; }
    if (sub913_month > 12) { sub913_month = 1;  sub913_year += 1; }
    sub913_load();
}

function sub913_moveToday() {
    sub913_year = gf_913_init.year;
    sub913_month = gf_913_init.month;
    sub913_load();
}

function sub913_load() {
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: { getMode: 'get', year: sub913_year, month: sub913_month },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (res) {
        if (!res.get_success) {
            Swal.fire('エラー', res.err_message, 'error');
            return;
        }
        sub913_days = res.days;
        $('#txt_month').text(res.year + '年 ' + res.month + '月');
        sub913_render(res.lead_blanks, res.days);
    }).fail(function () {
        Swal.fire('エラー', 'カレンダーを取得できませんでした。', 'error');
    }).always(function () {
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

// 1日分のセルに表示するタグを組み立てる
function sub913_buildTags(d) {
    var html = '';
    if (d.holiday_flg)  { html += '<span class="gf_cal_tag gf_tag_holiday">祝</span>'; }
    if (d.tokubetu_flg) { html += '<span class="gf_cal_tag gf_tag_tokubetu">特</span>'; }

    if (d.closed_flg) {
        html += '<span class="gf_cal_tag gf_tag_closed">休</span>';
    } else if (d.closed_slots.length > 0) {
        // 計画かどうかで色を変え、どの時間帯が休業かを併記する
        var cls = (d.reason === 'planned') ? 'gf_tag_temp' : 'gf_tag_unplanned';
        var names = d.closed_slots.map(function(s) { return SUB913_SLOT_NAMES[s] || s; }).join('');
        html += '<span class="gf_cal_tag ' + cls + '">' + names + '</span>';
    }
    return html;
}

function sub913_render(pLeadBlanks, pDays) {
    var html = '';
    var col = 0;

    html += '<tr>';
    for (var i = 0; i < pLeadBlanks; i++) {
        html += '<td class="gf_cal_blank"></td>';
        col++;
    }

    pDays.forEach(function(d) {
        if (col === 7) { html += '</tr><tr>'; col = 0; }

        var editable = gf_913_init.allowPastEdit || !d.is_past;
        var cls = [];
        if (editable) { cls.push('gf_cal_editable'); }
        // グレー表示は「編集できない」ことを示す。過去日を編集できる設定の
        // ときにグレーにすると、押せるのに押せなさそうに見えてしまう。
        if (d.is_past && !editable) { cls.push('gf_cal_past'); }
        if (d.is_today) { cls.push('gf_cal_today'); }

        // 祝日は曜日に関わらず赤。土日はそれぞれの色。
        var numCls = '';
        if (d.holiday_flg) { numCls = 'gf_cal_holiday'; }
        else if (d.weekday === 5) { numCls = 'gf_cal_sat'; }
        else if (d.weekday === 6) { numCls = 'gf_cal_sun'; }

        html += '<td class="' + cls.join(' ') + '"'
              + (editable ? ' onclick="sub913_openEdit(' + d.day + ')"' : '') + '>'
              + '<span class="gf_cal_daynum ' + numCls + '">' + d.day + '</span>'
              + '<div class="gf_cal_marks">' + sub913_buildTags(d) + '</div>'
              + (d.memo ? '<div class="gf_cal_memo" title="' + sub913_escape(d.memo) + '">'
                          + sub913_escape(d.memo) + '</div>' : '')
              + '</td>';
        col++;
    });

    while (col < 7 && col > 0) { html += '<td class="gf_cal_blank"></td>'; col++; }
    html += '</tr>';

    $('#cal_body').html(html);
}

function sub913_escape(pText) {
    return $('<div>').text(pText).html();
}

function sub913_findDay(pDay) {
    for (var i = 0; i < sub913_days.length; i++) {
        if (sub913_days[i].day === pDay) { return sub913_days[i]; }
    }
    return null;
}

// 編集フォームは非表示テンプレートを複製して使うため、同じidの要素がページ内に
// 2つ存在する。$('#xxx') はDOM順で先にあるテンプレート側を拾ってしまうので、
// ダイアログ内に限定して要素を探すこと。
function sub913_$(pSelector) {
    var popup = Swal.getPopup();
    return popup ? $(popup).find(pSelector) : $();
}

// 終日休業を選んだら時間帯の選択は不要になる
function sub913_onToggleClosed() {
    var closed = sub913_$('#ed_closed').is(':checked');
    sub913_$('#ed_slot_area').toggle(!closed);
    if (closed) { sub913_$('.ed_slot').prop('checked', false); }
    sub913_onToggleSlot();
}

// 休業が無い日は理由を選ばせない
function sub913_onToggleSlot() {
    var hasClosure = sub913_$('#ed_closed').is(':checked')
                  || sub913_$('.ed_slot:checked').length > 0;
    sub913_$('#ed_reason_area').toggle(hasClosure);
}

function sub913_openEdit(pDay) {
    var d = sub913_findDay(pDay);
    if (!d) { return; }

    Swal.fire({
        title: d.business_day + ' の設定',
        html: $('#edit_form_template').html(),
        width: 520,
        showCancelButton: true,
        confirmButtonText: '保存',
        cancelButtonText: 'キャンセル',
        didOpen: () => {
            // SweetAlert2 が複製した要素に対して初期値を流し込む
            sub913_$('#ed_holiday').prop('checked', d.holiday_flg);
            sub913_$('#ed_tokubetu').prop('checked', d.tokubetu_flg);
            sub913_$('#ed_closed').prop('checked', d.closed_flg);
            sub913_$('.ed_slot').each(function() {
                $(this).prop('checked', d.closed_slots.indexOf($(this).val()) >= 0);
            });
            sub913_$('input[name="ed_reason"][value="' + (d.reason || 'planned') + '"]')
                .prop('checked', true);
            sub913_$('#ed_memo').val(d.memo);
            sub913_onToggleClosed();
        },
        preConfirm: () => {
            var slots = [];
            sub913_$('.ed_slot:checked').each(function() { slots.push($(this).val()); });
            return {
                holiday_flg:  sub913_$('#ed_holiday').is(':checked'),
                tokubetu_flg: sub913_$('#ed_tokubetu').is(':checked'),
                closed_flg:   sub913_$('#ed_closed').is(':checked'),
                closed_slots: slots,
                reason:       sub913_$('input[name="ed_reason"]:checked').val(),
                memo:         sub913_$('#ed_memo').val()
            };
        }
    }).then((result) => {
        if (result.isConfirmed) {
            sub913_postSave(d.business_day, result.value);
        }
    });
}

function sub913_postSave(pBusinessDay, pEntry) {
    if (typeof NProgress != 'undefined') { NProgress.start(); }

    $.ajax({
        type: "POST",
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode: 'save',
            businessDay: pBusinessDay,
            entry: JSON.stringify(pEntry)
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
        }
    }).done(function (res) {
        if (res.save_success) {
            // 保存できた月を読み直して表示を揃える
            sub913_load();
            Swal.fire({ title: '保存しました', text: res.err_message, icon: 'success',
                        timer: 1600, showConfirmButton: false });
        } else {
            Swal.fire('保存できませんでした', res.err_message, 'error');
        }
    }).fail(function () {
        Swal.fire('エラー', '通信に失敗しました。', 'error');
    }).always(function () {
        if (typeof NProgress != 'undefined') { NProgress.done(); }
    });
}

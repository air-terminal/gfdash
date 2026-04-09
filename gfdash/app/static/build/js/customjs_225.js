var GfTable = null;


function initFor225(){
    let initParam = {
        getMode:'init',
        getTableOption:'op_uriage',
        getChartMode: sub225_getToggleBtnOption()
    };

    // icheck使用部のイベントリスナー定義
    $('input').on('ifChecked', function(event){
        switch($(this).attr('name')){
            case 'table_option':
                btnToggleTableOption();
            break;
        }
    });

    sub225_postView(initParam);
}

function sub225_postView(initParam){

    // 初期データをview.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
            getTableOption : initParam.getTableOption,
            getChartMode: initParam.getChartMode,
            getY : initParam.getY
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
            // NProgress処理
            if (typeof NProgress != 'undefined') {
                NProgress.start();
            }   
        },
    }).done(function (results) {
        // ***** とりあえずindex用。　ページが増えたら考えること
        var tmp = [];
        var tmpBaseAll = 0;

        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'txtHeader':
                    $("#gf_header").text(val + '売上比較');
                    break;
                case 'table':
                    $.each(val, function(key2, val2) {
                        var tmp2 = [];
                    
                        $.each(val2, function(key3, val3) {
                            tmp2[key3] = val3;
                        });

                        tmp.push(tmp2);
                    });

                    break;
                case 'tableSum':
                    switch(sub220_getTableOption()){
                        case 'op_nyukin':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt02").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt03").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt04").text(val2);
                                        break;
                                    case 'bukatu':
                                        $("#txt111").text(val2);
                                        break;
                                    case 'kaihi':
                                        $("#txt112").text(val2);
                                        break;
                                    case 'nyukin':
                                        $("#txt113").text(val2);
                                        break;
                                }
                            });                        
                            break;
                        case 'op_sonota':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt02").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt03").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt04").text(val2);
                                        break;
                                    case 'sagaku':
                                        $("#txt111").text(val2);
                                        break;
                                    case 'ken':
                                        $("#txt112").text(val2);
                                        break;
                                    case 'line':
                                        $("#txt113").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                        default:
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt02").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt03").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt04").text(val2);
                                        break;
                                    case 'range':
                                        $("#txt111").text(val2);
                                        break;
                                    case 'school':
                                        $("#txt112").text(val2);
                                        break;
                                    case 'shop':
                                        $("#txt113").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                    }         
                    break;
                case 'initYMD':
                    $("#calendar_initval").val(val);
                    break;
                case 'firstDay':
                    $("#calendar_from").val(val);
                    break;
                case 'lastDay':
                    $("#calendar_to").val(val);
                    break;
                case 'BaseAll':
                    tmpBaseAll = val;
                    break;
                default:
                    console.log('unknown key:' + key);
                    break;
            }
        });

        // グラフの表示
        sub225_setChartData(tmp, tmpBaseAll);

        // 表の表示
        sub225_drawTable(tmp);
        sub225_editColor();

        // datepickerの設定
        sub225_setDatepicker(initParam.getMode);

        //ボタンの設定
        var initDate = new Date($("#calendar_initval").val());
        var fromDate = new Date($("#calendar_from").val());
        var toDate = new Date($("#calendar_to").val());

        fromDate.setDate(1);
        toDate.setDate(1);

        if (initDate.getTime() > fromDate.getTime()){
            $('#tbn_prev_month').prop('disabled',false);
        } else {
            $('#tbn_prev_month').prop('disabled',true);
        }

        if (initDate.getTime() < toDate.getTime()){
            $('#tbn_next_month').prop('disabled',false);
        } else {
            $('#tbn_next_month').prop('disabled',true);
        }

    }).fail(function (jqXHR, textStatus, errorThrown) {
        // 通信失敗時の処理
        console.log("ajax通信に失敗しました");
        console.log("jqXHR          : " + jqXHR.status); // HTTPステータスが取得
        console.log("textStatus     : " + textStatus);    // タイムアウト、パースエラー
        console.log("errorThrown    : " + errorThrown.message); // 例外情報
    });

    // NProgress終了処理
    if (typeof NProgress != 'undefined') {
        NProgress.done();
    }   

    return false;
}


function sub225_setChartData(dataTbl, tmpBaseAll){
    //値設定処理

    if (typeof(Chart) === 'undefined') {
        console.log('Chart undefined');
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var data_len = $(dataTbl).length - 1;
    if(data_len < 0){
        data_len = 0;
    }

    var tmpXLabels = [];
    var tmpData1 = [];

    var tmpSuggestedMinY = tmpBaseAll;

    // 売上
    var i = 0;
    for (var j in dataTbl) {
        tmpData1.push(dataTbl[j]['all']);
        if (tmpSuggestedMinY > dataTbl[j]['all']){
            tmpSuggestedMinY = dataTbl[j]['all'];
        }
        i += 1;
    };

    i = 0;
    for (var j in dataTbl) {
        tmpXLabels.push(dataTbl[j]['YYYY']);
        i += 1;
    };

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 10000000) * 10000000 - 10000000; 
    if(tmpSuggestedMinY < 0){
        tmpSuggestedMinY = 0;
    }

    if (!$("#chart_plot_mix").length) {
        return;
    };

    var ctx = document.getElementById("chart_plot_mix");
    window.Chart1 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tmpXLabels,
            datasets: [{
                order: 10,
                label: "年間総売上",
                backgroundColor: "rgba(38, 185, 154, 0.7)",
                borderColor: "rgba(38, 185, 154, 0.7)",
                pointBorderColor: "rgba(38, 185, 154, 0.7)",
                pointBackgroundColor: "rgba(38, 185, 154, 0.7)",
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(220,220,220,1)",
                pointBorderWidth: 1,
                fill: true,
                data: tmpData1,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
            }]
        },
        options: {
            scales: {
                y1: {
                    type: 'linear',
                    position: 'left',
                    title:{
                        display: false
                    },
                    min: tmpSuggestedMinY
                }
            },
            plugins:{
                annotation: {
                    annotations: {
                        line1: {
                            type: 'line',
                            yMin: tmpBaseAll,
                            yMax: tmpBaseAll,
                            borderColor: "rgba(3, 88, 106, 0.70)",
                            borderWidth: 2,
                            label: {
                                enabled: true
                            }
                        },
                    }
                }
            }
        }
    });

}

function sub225_drawTable(jsonData){

    var tmpColums = [];
    // 8列構成用の幅配分 (合計100%)
    var colWidths = ["10%", "13%", "10%", "11%", "11%", "11%", "17%", "17%"];

    jsonData.reverse();

    switch(sub225_getTableOption()){
        case 'op_nyukin':
            $("#txt001").text("入金");
            $("#txt011").text("部活動等");
            $("#txt012").text("年会費");
            $("#txt013").text("試打会等");
            tmpColums = [
                {data:"LabelY",   width: colWidths[0]},
                {data:"aridaka",  width: colWidths[1]},
                {data:"shukkin",  width: colWidths[2]},
                {data:"bukatu",   width: colWidths[3]},
                {data:"kaihi",    width: colWidths[4]},
                {data:"nyukin",   width: colWidths[5]},
                {data:"all",      width: colWidths[6]},
                {data:"compAll",  width: colWidths[7]}
            ];
            break;
        case 'op_sonota':
            $("#txt001").text("その他");
            $("#txt011").text("過不足");
            $("#txt012").text("券");
            $("#txt013").text("LINE");
            tmpColums = [
                {data:"LabelY",   width: colWidths[0]},
                {data:"aridaka",  width: colWidths[1]},
                {data:"shukkin",  width: colWidths[2]},
                {data:"sagaku",   width: colWidths[3]},
                {data:"ken",      width: colWidths[4]},
                {data:"line",     width: colWidths[5]},
                {data:"all",      width: colWidths[6]},
                {data:"compAll",  width: colWidths[7]}
            ];
            break;
        default:
            $("#txt001").text("売上部門");
            $("#txt011").text("レンジ");
            $("#txt012").text("スクール");
            $("#txt013").text("ショップ");
            tmpColums = [
                {data:"LabelY",   width: colWidths[0]},
                {data:"aridaka",  width: colWidths[1]},
                {data:"shukkin",  width: colWidths[2]},
                {data:"range",    width: colWidths[3]},
                {data:"school",   width: colWidths[4]},
                {data:"shop",     width: colWidths[5]},
                {data:"all",      width: colWidths[6]},
                {data:"compAll",  width: colWidths[7]}
            ];
            break;
    }

    var table=$('#datatable_gf').DataTable({
        'data'        :jsonData,
        'paging'      :false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :false, // 重要：自動計算を無効化
        'scrollX'     :false, // 重要：100%幅で固定するためOFF
        destroy: true,
        'columns'     :tmpColums,

    });

    // 描画後に幅を再調整してヘッダと同期させる
    setTimeout(function(){
        table.columns.adjust();
    }, 50);

}

function sub225_setDatepicker(getMode){

    if (getMode === 'init'){
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
    
        // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
        $.fn.datepicker.defaults.language = 'ja';
        $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
        $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
        $.fn.datepicker.defaults.minViewMode = 2;
        $.fn.datepicker.defaults.maxViewMode = 2;
        $.fn.datepicker.defaults.format = 'yyyy年';
        $.fn.datepicker.defaults.autoclose = true;
    
        sub225_init_daterangepicker_single_call_gf();
    
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年');
    
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        var month = (newDate.getMonth() + 1).toString();
        $("#gf_calendar").val(year + '年');
    }

    $("#calendar_saveval").val($("#gf_calendar").val());

}

function sub225_init_daterangepicker_single_call_gf() {

    if (typeof($.fn.datepicker) === 'undefined') {
        return;
    }
    
    $('.input-group.date').datepicker({
        format: 'yyyy年',
        minViewMode: 2,
        keyboardNavigation: false,
        autoclose: true
    }).on({
        changeDate:
          function(obj) {

            $("#calendar_saveval").val($("#gf_calendar").val());

            let initParam = {
                getMode:'get',
                getChartMode: sub225_getToggleBtnOption(),
                getTableOption : sub225_getTableOption(),
                getY:convStrDateTime(obj.date) + ' 00:00:00'
            };
        
            sub225_postView(initParam);

            var newDate = new Date(initParam.getY);
            var year = newDate.getFullYear().toString().padStart(4, '0');
            $("#gf_calendar").val(year + '年');
            $("#calendar_saveval").val($("#gf_calendar").val());
            
        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}

function btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 12);

    let initParam = {
        getMode:'get',
        getChartMode: sub225_getToggleBtnOption(),
        getTableOption : sub225_getTableOption(),
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);
    sub225_postView(initParam);

}

function btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 12);

    let initParam = {
        getMode:'get',
        getChartMode: sub225_getToggleBtnOption(),
        getTableOption : sub225_getTableOption(),
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub225_postView(initParam);
}

function btnToggleTableOption(){
    // グラフ表示切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getChartMode: sub225_getToggleBtnOption(),
        getTableOption : sub225_getTableOption(),
        getY:convStrDateTime(getDate) + ' 00:00:00'
    };

    sub225_postView(initParam);

}

function convStrDateTime(pDateTime){
    var year = pDateTime.getFullYear().toString().padStart(4, '0');
    var month = (pDateTime.getMonth() + 1).toString().padStart(2, '0');
    var day = pDateTime.getDate().toString().padStart(2, '0');
    return (year + '/' + month + '/' + day);
}

function sub225_editColor(){
    $('.dt-scroll-body td').filter(function() {
        return parseInt($(this).text()) < 0;
    }).addClass('minus');
    $('.dt-scroll-foot td').filter(function() {
        return parseInt($(this).text()) < 0;
    }).addClass('minus');
    $('.dt-scroll-foot td').filter(function() {
        return parseInt($(this).text()) >= 0;
    }).removeClass('minus');

}

function sub225_getTableOption(){
    var result = $('input[name="table_option"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}

function sub225_getToggleBtnOption(){
    var result = $('input[name="chart_mode"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}

// 初期処理
$(document).ready(function() {
    initFor225();
});


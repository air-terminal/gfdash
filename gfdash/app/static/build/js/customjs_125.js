/*
    各画面専用javascript
    125nenji_hikaku.html
    ※命名規則　sub125_xxxxxx (パッケージ等の共通関数と重複させない為)
*/


function initFor125(){
    // getKikan: 1(上期12-5),2(下期5-11),3(通期12-11),5(年間1-12)

    let initParam = {
        getMode:'init',
        getChartMode: sub125_getToggleBtnOption(),
    };

    sub125_postView(initParam);
}


function sub125_postView(initParam){

    // view.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
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
        var tmp = [];
        var dataTbl = [];
        var allDataTbl = [];
        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'txtHeader':
                    switch(sub125_getToggleBtnOption()){
                        case 'nenkan':
                            $("#gf_header").text(val + '年間来場者数');
                            break;
                        case 'kamiki':
                            $("#gf_header").text(val + '上期来場者数');
                            break;
                        case 'simoki':
                            $("#gf_header").text(val + '下期来場者数');
                            break;
                    }
                    break;
                case 'school1_name':
                    $("#school1-1").text(val);
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
                case 'yearTable':
                    dataTbl = val;
                    break;
                case 'allYearTable':
                    allDataTbl = val;
                    break;
                default:
                    console.log('unknown key:' + key);
                    break;
            }
        });
                
        // グラフ処理
        sub125_setChartData(dataTbl, allDataTbl);

        // 表の表示
        sub125_drawTable(dataTbl, allDataTbl);
        com_tableDataEditColor();

        // datepickerの設定
        sub125_setDatepicker(initParam.getMode);

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



function sub125_setChartData(dataTbl, allDataTbl){
    //　グラフ表示処理

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

    var tmpHanrei1 = '';
    switch(sub125_getToggleBtnOption()){
        case 'nenkan':
            tmpHanrei1 = '年間来場者数';
            break;
        case 'kamiki':
            tmpHanrei1 = '上期(12-5月)来場者数';
            break;
        case 'simoki':
            tmpHanrei1 = '下期(6-11月)来場者数';
            break;
    }

    var tmpXLabels = [];
    var tmpData1 = [];
    var tmpSuggestedMinY = 0;
    var tmpBaseAll = 0;

    // Y軸最小値(仮)
    $.each(dataTbl, function(key, val) {
        tmpSuggestedMinY = val['all'];
        tmpBaseAll = val['all'];
    });
    
    // 月別来場者数
    $.each(allDataTbl, function(key, val) {
        tmpXLabels.push(key + '年');
        tmpData1.push(val['all']);
        if (tmpSuggestedMinY > val['all']){
            tmpSuggestedMinY = val['all'];
        }
    });

    // Y軸表記最小値計算
    tmpSuggestedMinY = Math.floor(tmpSuggestedMinY / 1000) * 1000 - 1000; 
    if(tmpSuggestedMinY < 0){
        tmpSuggestedMinY = 0;
    }

    if (!$("#chart_plot_mix").length) {
        return;
    }

    var ctx = document.getElementById("chart_plot_mix");
    window.Chart1 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tmpXLabels,
            datasets: [{
                order: 10,
                label: tmpHanrei1,
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


function sub125_setDatepicker(getMode){

    if (getMode === 'init'){
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        var month = (newDate.getMonth() + 1).toString();
    
        // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
        $.fn.datepicker.defaults.language = 'ja';
        $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
        $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
        $.fn.datepicker.defaults.minViewMode = 2;
        $.fn.datepicker.defaults.maxViewMode = 2;
        $.fn.datepicker.defaults.format = 'yyyy年';
        $.fn.datepicker.defaults.autoclose = true;
    
        sub125_init_daterangepicker_single_call_gf();
    
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年');
    
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
        $("#gf_calendar").val(year + '年');
    }

    $("#calendar_saveval").val($("#gf_calendar").val());

}

function sub125_init_daterangepicker_single_call_gf() {

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
                getChartMode: sub125_getToggleBtnOption(),
                getY:com_convStrDateTime(obj.date) + ' 00:00:00'
            };
        
            sub125_postView(initParam);

            var newDate = new Date(initParam.getY);
            var year = newDate.getFullYear().toString().padStart(4, '0');
//            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年');
            $("#calendar_saveval").val($("#gf_calendar").val());

        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}


function sub125_drawTable(dataTbl, allDataTbl){

    var tmpBaseSum = 0;
    var tmpBaseYear = '';

    // ベースデータの取得
    $.each(dataTbl, function(key, val) {
        tmpBaseYear = key;
        $.each(val, function(key2, val2) {
            if(key2 === 'all'){
                tmpBaseSum = val2;
            }
        });
    });

    // 表データの生成
    var tmpData = [];
    $.each(allDataTbl, function(key, val) {

        var tmp = [];
        if(key === tmpBaseYear){
            tmp['business_y'] = '▶' + key + '年';
            $("#default_year").text(key + '年比');
        } else {
            tmp['business_y'] = key + '年';
        };

        $.each(val, function(key2, val2) {
            tmp[key2] = val2;
        });
        tmp['hikaku'] = tmpBaseSum - val['all'];
        tmpData.push(tmp);

    });

    tmpData.reverse();

    var table=$('#datatable_gf').DataTable({
        'data'        :tmpData,
        'paging'      :false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :false, // 重要：自動計算を無効にする
        'destroy'     :true,
        'columns'     :[
            {data:"business_y",      width: "10.6%"}, // 年
            {data:"morning",         width: "9.1%"}, // 朝
            {data:"afternoon",       width: "9.1%"}, // 昼
            {data:"night",           width: "9.1%"}, // 夜
            {data:"school",          width: "9.6%"},   // スクール
            {data:"int_school",      width: "10.1%"}, // (内部S)
            {data:"member",          width: "9.6%"},   // メンバー
            {data:"visitor",         width: "9.6%"},   // ビジター
            {data:"all",             width: "11.6%"},  // 合計
            {data:"hikaku",          width: "11.6%"}   // 基準比
        ]
    }).on( 'draw.dt', function () {
        com_tableDataEditColor();
    });

    // 描画完了後に列幅を再調整（ズレ防止の決定打）
    setTimeout(function(){
        table.columns.adjust();
    }, 50);
}

function sub125_btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 12);

    let initParam = {
        getMode:'get',
        getChartMode: sub125_getToggleBtnOption(),
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);
    sub125_postView(initParam);

}

function sub125_btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 12);

    let initParam = {
        getMode:'get',
        getChartMode: sub125_getToggleBtnOption(),
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub125_postView(initParam);

}

function btnToggleTableOption(){
    // グラフ表示切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getChartMode: sub125_getToggleBtnOption(),
        getY:com_convStrDateTime(getDate) + ' 00:00:00'
    };

    sub125_postView(initParam);

}

function sub125_getToggleBtnOption(){
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
        initFor125();
    });
    

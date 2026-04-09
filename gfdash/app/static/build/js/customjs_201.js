/*
    各画面専用javascript
    画面名：index.html
    ※命名規則　sub201_xxxxxx (パッケージ等の共通関数と重複させない為)
*/


function initFor201(){

    $("#status_014_2").hide();
    $("#nenkaihi_option").hide();
    $("#detail_option").hide();
    $("#detail2_option").hide();

    let initParam = {
        getMode:'init',
        getChartMode: sub201_getChartMode()
    };

    sub201_postView(initParam);

    // icheck使用部のイベントリスナー定義
    $('input').on('ifChecked', function(event){
        switch($(this).attr('name')){
            case 'range_option':
                btnToggleNenkaihi();
            break;
        }
    });

    $('input').on('ifToggled', function(event){
        switch($(this).attr('name')){
            case 'detail_option':
                chkDetailChartMode();
            break;
        }
    });

    $('input').on('ifChecked', function(event){
        switch($(this).attr('name')){
            case 'detail2_option':
                btnToggleDetail2();
            break;
        }
    });

}


function sub201_postView(postParam){

    // 初期データをview.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : postParam.getMode,
            getYM : postParam.getYM,
            getChartMode : postParam.getChartMode
        },
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
            // NProgress処理
            if (typeof NProgress != 'undefined') {
                NProgress.start();
            }   
        },
    }).done(function (results) {
        // ***** とりあえずindex用。　ページが増えたら考えること
        var chartResults2 = [];
        var chartResultsSum2 = [];
        var chartResultsOld2 = [];
        var chartResultsOldSum2 = [];
        var chartPreResults = [];
        var tmpSum = 0;
        var tmpOldSum = 0;

        var detailSum = {all:0, range:0, shop:0, school:0, nyukin:0, ave:0, kaihi:0};
        var detailSumOld = {all:0, range:0, shop:0, school:0, nyukin:0, ave:0, kaihi:0};

        var pDate = '';
        var tmpDetail = {all:0, range:0, shop:0, school:0, nyukin:0, ave:0, kaihi:0};

        var chartXLabels = [];
//        var chartHeinenTemp = [];

        var chartResultsDetail = {range:[], shop:[], school:[], nyukin:[], other:[], kaihi:[]};
        var tmpRange = 0;
        var tmpShop = 0;
        var tmpSchool = 0;
        var tmpNyukin = 0;
        var tmpOther = 0;
        var tmpKaihi = 0;
                                
        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'header':
                    $(".txt001").text(val);
                    break;
                case 'reportrange':
                    $('#reportrange001 span').html(val);
                case 'initYMD':
                    $("#calendar_initval").val(val);
                    break;
                case 'firstDay':
                    $("#calendar_from").val(val);
                    break;
                case 'lastDay':
                    $("#calendar_to").val(val);
                    break;
                case 'startDate':
                    startDate = moment(new Date(val).getTime());
                    break;
                case 'endDate':
                    endDate = moment(new Date(val).getTime());
                    break;
                case 'detail':
                    $.each(val, function(key2, val2) {
                        tmpDetail['all'] = 0;
                        tmpDetail['range'] = 0;
                        tmpDetail['shop'] = 0;
                        tmpDetail['school'] = 0;
                        tmpDetail['nyukin'] = 0;
                        tmpDetail['kaihi'] = 0;

                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'business_day':
                                    pDate = val3.substr(5);
                                    break;
                                case 'all':
                                    tmpDetail['all'] = val3;
                                    break;
                                case 'range':
                                    tmpDetail['range'] = val3;
                                    break;
                                case 'shop':
                                    tmpDetail['shop'] = val3;
                                    break;
                                case 'school':
                                    tmpDetail['school'] = val3;
                                    break;
                                case 'nyukin':
                                    tmpDetail['nyukin'] = val3;
                                    break;
                                case 'kaihi':
                                    tmpDetail['kaihi'] = val3;
                                    break;
                            };
                        });
                        // グラフにプロットする際、取得したDB上は世界標準時なので日本時間に合わせる。
                        tmpSum = tmpSum + Number(tmpDetail['all']);

                        //グラフ表示モードによりデータをセットする
                        switch(postParam.getChartMode){
                            case 'total':
                                chartResults2.push([pDate, tmpDetail['all']]);
                                chartResultsSum2.push([pDate, tmpSum]);    
                                break;
                            case 'detail':
                                tmpRange = 0;
                                tmpShop = 0;
                                tmpSchool = 0;
                                tmpNyukin = 0;
                                tmpKaihi = 0;
                                tmpOther = tmpDetail['all'];

                                if ($('#detail_option1').prop('checked')){
                                    tmpRange = tmpDetail['range'];
                                    tmpOther -= tmpDetail['range'];
                                };
                                if ($('#detail_option2').prop('checked')){
                                    tmpShop = tmpDetail['shop'];
                                    tmpOther -= tmpDetail['shop'];
                                };
                                if ($('#detail_option3').prop('checked')){
                                    tmpSchool = tmpDetail['school'];
                                    tmpOther -= tmpDetail['school'];
                                };

                                if (sub201_getRangeOption() === 'nenkaihi_add'){
                                    if ($('#detail_option4').prop('checked')){
                                        tmpNyukin = tmpDetail['nyukin'];
                                        tmpOther -= tmpDetail['nyukin'];
                                    };
                                } else {
                                    if ($('#detail_option4').prop('checked')){
                                        tmpNyukin = tmpDetail['nyukin'] - tmpDetail['kaihi'];
                                        tmpOther -= (tmpDetail['nyukin']- tmpDetail['kaihi']);
                                    };
                                };

                                if (sub201_getRangeOption() === 'nenkaihi_separate'){
                                    if ($('#detail_option10').prop('checked')){
                                        tmpKaihi = tmpDetail['kaihi'];
                                        tmpOther -= tmpDetail['kaihi'];
                                    };
                                };

                                chartResultsDetail['range'].push([pDate, tmpRange]);
                                chartResultsDetail['shop'].push([pDate, tmpShop]);
                                chartResultsDetail['school'].push([pDate, tmpSchool]);
                                chartResultsDetail['nyukin'].push([pDate, tmpNyukin]);
                                chartResultsDetail['other'].push([pDate, tmpOther]);
                                chartResultsDetail['kaihi'].push([pDate, tmpKaihi]);

                                break;
                        };
                    });
                    break;
                case 'detailSum':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                detailSum['all'] = val2;
                                break;
                            case 'range':                                
                                detailSum['range'] = val2;
                                break;
                            case 'shop':
                                detailSum['shop'] = val2;
                                break;
                            case 'school':
                                detailSum['school'] = val2;
                                break;
                            case 'nyukin':
                                detailSum['nyukin'] = val2;
                                break;
                            case 'kaihi':
                                detailSum['kaihi'] = val2;
                                break;
                            case 'ave':
                                detailSum['ave'] = val2;
                                break;
                        };
                    });

                    if (sub201_getRangeOption() === 'nenkaihi_separate'){
                        detailSum['nyukin'] -= detailSum['kaihi'];
                    };

                    break;
                case 'detailSumOld':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                detailSumOld['all'] = val2;
                                break;
                            case 'range':
                                detailSumOld['range'] = val2;
                                break;
                            case 'shop':
                                detailSumOld['shop'] = val2;
                                break;
                            case 'school':
                                detailSumOld['school'] = val2;
                                break;
                            case 'nyukin':
                                detailSumOld['nyukin'] = val2;
                                break;
                            case 'kaihi':
                                detailSumOld['kaihi'] = val2;
                                break;
                            case 'ave':
                                detailSumOld['ave'] = val2;
                                break;
                        };
                    });

                    if (sub201_getRangeOption() === 'nenkaihi_separate'){
                        detailSumOld['nyukin'] -= detailSumOld['kaihi'];
                    };

                    break;
                case 'preYear':
                    $.each(val, function(key2, val2) {
                        chartPreResults.push([
                            key2.substr(5), val2
                        ]);
                    });
                    break;
                case 'oldYear':
                    $.each(val, function(key2, val2) {
                        // グラフにプロットする際、取得したDB上は世界標準時なので日本時間に合わせる。
                        tmpOldSum = tmpOldSum + Number(val2);
                        chartResultsOld2.push([
                            key2.substr(5), val2
                        ]);
                        chartResultsOldSum2.push([
                            key2.substr(5), tmpOldSum
                        ]);    
                    });
                    break;
                case 'xLabel':
                    $.each(val, function(key2, val2) {
                        chartXLabels.push([
                            val2
                        ]);
                    });
                    break;

                case 'tb120_lastday':
                    $(".txt302").text(val);
                    break;
                default:
                    break;
            }
        });
        // オプション表示設定
        if(postParam.getChartMode === 'detail'){
            sub201_set_chatjs_detail(chartXLabels, chartResultsDetail);
            $("#nenkaihi_option").show();
            $("#detail_option").show();
            $("#detail2_option").show();
        } else {
            sub201_set_chatjs_gf(chartXLabels, chartResults2, chartResultsSum2, chartResultsOldSum2, chartPreResults);
            $("#nenkaihi_option").hide();
            $("#detail_option").hide();
            $("#detail2_option").hide();
        }

        if (postParam.getMode === 'init'){
            var newDate = new Date($("#calendar_initval").val());
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
        
            // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
            $.fn.datepicker.defaults.language = 'ja';
            $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
            $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
            $.fn.datepicker.defaults.minViewMode = 1;
            $.fn.datepicker.defaults.maxViewMode = 2;
            $.fn.datepicker.defaults.format = 'yyyy年MM';
            $.fn.datepicker.defaults.autoclose = true;
        
            sub201_init_daterangepicker_single_call_gf();
        
            $('.input-group.date').datepicker('update', newDate);
            $("#gf_calendar").val(year + '年' + month + '月');
        
        } else {
            var newDate = new Date($("#calendar_initval").val());
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年' + month + '月');
        }

        // サマリーデータ表示
        sub201_set_summaryData(detailSum, detailSumOld);

        $("#calendar_saveval").val($("#gf_calendar").val());
        sub201_set_btn();

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




function sub201_init_daterangepicker_single_call_gf() {

    if (typeof($.fn.datepicker) === 'undefined') {
        return;
    }
    
    $('.input-group.date').datepicker({
        format: 'yyyy年MM',
        minViewMode: 'months',
        keyboardNavigation: false,
        autoclose: true
    }).on({
        changeDate:
          function(obj) {
            var result = $('input[name="chart_mode"]:checked');
            var chartMode = null
            for(i=0; i<result.length; i++) {
                if(result[i].checked) {
                    chartMode = result[i].value;
                }
            }

            $("#calendar_saveval").val($("#gf_calendar").val());

            let initParam = {
                getMode:'get',
                getYM:com_convStrDateTime(obj.date) + ' 00:00:00',
                getChartMode:chartMode
            };
        
            sub201_postView(initParam);

            var newDate = new Date(initParam.getYM);
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年' + month + '月');
            $("#calendar_saveval").val($("#gf_calendar").val());

        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}

function btnPrevMonth(){

    // 折れ線グラフ部
    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub201_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub201_postView(initParam);

    var newDate = new Date(initParam.getYM);
    var year = newDate.getFullYear().toString().padStart(4, '0');
    var month = (newDate.getMonth() + 1).toString();
    $("#gf_calendar").val(year + '年' + month + '月');
    $("#calendar_saveval").val($("#gf_calendar").val());

}

function btnNextMonth(){

    // 折れ線グラフ部
    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub201_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub201_postView(initParam);

    var newDate = new Date(initParam.getYM);
    var year = newDate.getFullYear().toString().padStart(4, '0');
    var month = (newDate.getMonth() + 1).toString();
    $("#gf_calendar").val(year + '年' + month + '月');
    $("#calendar_saveval").val($("#gf_calendar").val());

}

function btnToggleNenkaihi(){
    // 年会費の集計先切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub201_getChartMode()
    };

    sub201_postView(initParam);

    if (sub201_getRangeOption() === 'nenkaihi_add'){
        $("#detail_option_sub1").hide();
        $("#status_014_2").hide();
    } else {
        $("#detail_option_sub1").show();
        $("#status_014_2").show();
    }

}

function btnToggleDetail2(){
    // その他表示切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub201_getChartMode()
    };

    sub201_postView(initParam);

}


function chkDetailChartMode(){
    // 折れ線グラフ部　来場者数累計／気温の切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub201_getChartMode()
    };

    sub201_postView(initParam);

}

function sub201_set_btn(){
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
}

function sub201_set_summaryData(detailSum, detailSumOld){
    var hikakuAll = detailSum['all'] - detailSumOld['all'];
    var hikakuRange = detailSum['range'] - detailSumOld['range'];
    var hikakuShop = detailSum['shop'] - detailSumOld['shop'];
    var hikakuSchool = detailSum['school'] - detailSumOld['school'];
    var hikakuOther = detailSum['nyukin'] - detailSumOld['nyukin'];
    var hikakuAve = detailSum['ave'] - detailSumOld['ave'];
    var hikakuKaihi = detailSum['kaihi'] - detailSumOld['kaihi'];

    // レンジ売上
    $(".txt011").text(detailSum['range'].toLocaleString());
    $(".txt111").empty();
    $(".txt111").text(hikakuRange.toLocaleString());
    if (hikakuRange > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt111");
        $(".txt111").wrapInner('<i class="green" />');
    } else if(hikakuRange < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt111");
        $(".txt111").wrapInner('<i class="red" />');
    }

    // ショップ売上
    $(".txt012").text(detailSum['shop'].toLocaleString());
    $(".txt112").empty();
    $(".txt112").text(hikakuShop.toLocaleString());
    if (hikakuShop > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt112");
        $(".txt112").wrapInner('<i class="green" />');
    } else if(hikakuShop < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt112");
        $(".txt112").wrapInner('<i class="red" />');
    }

    // スクール売上
    $(".txt013").text(detailSum['school'].toLocaleString());
    $(".txt113").empty();
    $(".txt113").text(hikakuSchool.toLocaleString());
    if (hikakuSchool > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt113");
        $(".txt113").wrapInner('<i class="green" />');
    } else if(hikakuSchool < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt113");
        $(".txt113").wrapInner('<i class="red" />');
    }

    // 年会費
    $(".txt014_2").text(detailSum['kaihi'].toLocaleString());
    $(".txt114_2").empty();
    $(".txt114_2").text(hikakuKaihi.toLocaleString());
    if (hikakuKaihi > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt114_2");
        $(".txt114_2").wrapInner('<i class="green" />');
    } else if(hikakuKaihi < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt114_2");
        $(".txt114_2").wrapInner('<i class="red" />');
    }

    // その他
    $(".txt014").text(detailSum['nyukin'].toLocaleString());
    $(".txt114").empty();
    $(".txt114").text(hikakuOther.toLocaleString());
    if (hikakuOther > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt114");
        $(".txt114").wrapInner('<i class="green" />');
    } else if(hikakuOther < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt114");
        $(".txt114").wrapInner('<i class="red" />');
    }

    // 総売上
    $(".txt015").text(detailSum['all'].toLocaleString());
    $(".txt115").empty();
    $(".txt115").text(hikakuAll.toLocaleString());
    if (hikakuAll > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt115");
        $(".txt115").wrapInner('<i class="green" />');
    } else if(hikakuAll < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt115");
        $(".txt115").wrapInner('<i class="red" />');
    }

    // 平均売上額
    $(".txt016").text(detailSum['ave'].toLocaleString());
    var tmpYoY = Math.round(hikakuAve * 100) / 100;
    $(".txt116").empty();
    $(".txt116").text(tmpYoY.toLocaleString());
    if (tmpYoY > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt116");
        $(".txt116").wrapInner('<i class="green" />');
    } else if(tmpYoY < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt116");
        $(".txt116").wrapInner('<i class="red" />');
    }

}

function sub201_set_chatjs_gf(chartXLabels, chart_plot_02_data, chart_plot_02_data2, chart_plot_02_data3, chartPreResults) {
    //値設定処理

    if (typeof(Chart) === 'undefined') {
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var data_len = $(chart_plot_02_data).length - 1;
    if(data_len < 0){
        data_len = 0;
    }

    var tmpXLabels = [];
    var tmpData1 = [];
    var tmpData2 = [];
    var tmpData3 = [];
    var tmpData4 = [];
    var tmpLastData = 0;
    var i = 0;

    for (var key in chartXLabels) {
        tmpXLabels.push(chartXLabels[key][0]);
    };

    for (var key in chart_plot_02_data) {
//        tmpXLabels.push(chart_plot_02_data[key][0]);
        tmpData1.push(chart_plot_02_data[key][1]);
        tmpData4.push(null);
    };

    for (var key in chart_plot_02_data2) {
        tmpData2.push(chart_plot_02_data2[key][1]);
        tmpLastData = chart_plot_02_data2[key][1];
    };

    for (var key in chart_plot_02_data3) {
        tmpData3.push(chart_plot_02_data3[key][1]);
    };

    for (var key in chartPreResults) {
//        tmpXLabels.push(chartPreResults[key][0]);
        if (i == 0){
            tmpData4.pop();
            tmpData4.push(tmpLastData);
        }
        tmpData4.push(chartPreResults[key][1]);

        i = i + 1;
    };

    if ($("#chart_plot_02b").length) {
        var ctx = document.getElementById("chart_plot_02b");
        window.Chart1 = new Chart(ctx, {
            type: 'line',
            data: {
                labels: tmpXLabels,
                datasets: [{
                    order: 100,
                    label: "売上高",
//                    backgroundColor: "rgba(38, 185, 154, 0.31)",
                    backgroundColor: "rgba(38, 185, 154, 0.6)",
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
                }, {
                    order: 10,
                    label: "月次売上高",
                    backgroundColor: "rgba(3, 88, 106, 0.70)",
                    borderColor: "rgba(3, 88, 106, 0.70)",
                    pointBorderColor: "rgba(149, 169, 173, 0.7)",
                    pointBackgroundColor: "rgba(3, 88, 106, 0.70)",
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(3,88,106,0.70)",
                    pointBorderWidth: 1,
                    fill: false,
                    data: tmpData2,
                    yAxisID: 'y2'
                }, {
                    order: 15,
                    label: "前年月次売上高",
                    backgroundColor: "rgba(106, 65, 3, 0.7)",
                    borderColor: "rgba(106, 65, 3, 0.7)",
                    pointBorderColor: "rgba(149, 169, 173, 0.7)",
                    pointBackgroundColor: "rgba(106, 65, 3, 0.7)",
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(151,187,205,1)",
                    pointBorderWidth: 1,
                    fill: false,
                    data: tmpData3,
                    yAxisID: 'y2'
                }, {
                    order: 13,
                    label: "予測売上高",
                    backgroundColor: "rgba(255, 255, 255, 1)",
                    borderColor: "rgba(3, 88, 106, 0.70)",
                    borderDash: [5, 5],
                    pointBorderColor: "rgba(149, 169, 173, 0.7)",
                    pointBackgroundColor: "rgba(3, 88, 106, 0.70)",
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(3,88,106,0.70)",
                    pointBorderWidth: 1,
                    fill: false,
                    data: tmpData4,
                    yAxisID: 'y2'
                }]
            },

            options: {
                scales: {
                    x: {
                        ticks: {
                            autoSkip: false,
                            // コールバック関数を使ってラベルの色を動的に変更
                            color: function(context) {
                                return sub201_setChartLabelColor(context);
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        position: 'left',
                        title:{
                            display: true,
                            text: '売上高'
                        }
                    },
                    y2: {
                        display: true,
                        type: 'linear',
                        position: 'right',
                        title:{
                            display: true,
                            text: '売上高累計'
                        }
                    }
                }
            }
        });
    }
}



function sub201_set_chatjs_detail(chartXLabels, chartResultsDetail) {
    // グラフ設定処理（詳細）

    //値設定処理

    if (typeof(Chart) === 'undefined') {
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var tmpXLabels = [];

    var tmpDataX1 = [];
    var tmpDataX2 = [];
    var tmpDataX3 = [];
    var tmpDataX4 = [];
    var tmpDataX5 = [];
    var tmpDataX10 = [];
    var tmpDatasets = [];

    var tmpDataX1Color = "rgba(52,152,219,0.7)";
    var tmpDataX2Color = "rgba(231,76,60,0.7)";
    var tmpDataX3Color = "rgba(155,89,182,0.7)";
    var tmpDataX4Color = "rgba(247, 164, 69, 0.7)";
    var tmpDataX5Color = "rgba(48, 38, 185, 0.7)";
    var tmpDataX10Color = "rgba(38,185,154,0.7)";

    for (var key in chartXLabels) {
        tmpXLabels.push(chartXLabels[key][0]);
    }

    // 積み上げ棒グラフ設定
    if ($('#detail_option1').prop('checked')){
        for (var key in chartResultsDetail['range']) {
            tmpDataX1.push(chartResultsDetail['range'][key][1]);
        };

        tmpDatasets.push({
                    order: 100,
                    stack: 'stack1',
                    label: "レンジ",
                    backgroundColor: tmpDataX1Color,
                    borderColor: tmpDataX1Color,
                    pointBorderColor: tmpDataX1Color,
                    pointBackgroundColor: tmpDataX1Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX1,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }

    if ($('#detail_option2').prop('checked')){
        for (var key in chartResultsDetail['shop']) {
            tmpDataX2.push(chartResultsDetail['shop'][key][1]);
        };

        tmpDatasets.push({
                    order: 101,
                    stack: 'stack1',
                    label: "ショップ",
                    backgroundColor: tmpDataX2Color,
                    borderColor: tmpDataX2Color,
                    pointBorderColor: tmpDataX2Color,
                    pointBackgroundColor: tmpDataX2Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX2,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }

    if ($('#detail_option3').prop('checked')){
        for (var key in chartResultsDetail['school']) {
            tmpDataX3.push(chartResultsDetail['school'][key][1]);
        };

        tmpDatasets.push({
                    order: 102,
                    stack: 'stack1',
                    label: "スクール",
                    backgroundColor: tmpDataX3Color,
                    borderColor: tmpDataX3Color,
                    pointBorderColor: tmpDataX3Color,
                    pointBackgroundColor: tmpDataX3Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX3,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }

    if ($('#detail_option4').prop('checked')){
        for (var key in chartResultsDetail['nyukin']) {
            tmpDataX4.push(chartResultsDetail['nyukin'][key][1]);
        };

        tmpDatasets.push({
                    order: 103,
                    stack: 'stack1',
                    label: "入金",
                    backgroundColor: tmpDataX4Color,
                    borderColor: tmpDataX4Color,
                    pointBorderColor: tmpDataX4Color,
                    pointBackgroundColor: tmpDataX4Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX4,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    }

    if (sub201_getRangeOption() === 'nenkaihi_separate'){
        if ($('#detail_option10').prop('checked')){
            for (var key in chartResultsDetail['kaihi']) {
                tmpDataX5.push(chartResultsDetail['kaihi'][key][1]);
            };

            tmpDatasets.push({
                    order: 104,
                    stack: 'stack1',
                    label: "年会費",
                    backgroundColor: tmpDataX5Color,
                    borderColor: tmpDataX5Color,
                    pointBorderColor: tmpDataX5Color,
                    pointBackgroundColor: tmpDataX5Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX5,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
            });
        };
    }


    if (sub201_getDetail2Option() === 'view'){
        for (var key in chartResultsDetail['other']) {
            tmpDataX10.push(chartResultsDetail['other'][key][1]);
        };

        tmpDatasets.push({
                order: 105,
                stack: 'stack1',
                label: "その他",
                backgroundColor: tmpDataX10Color,
                borderColor: tmpDataX10Color,
                pointBorderColor: tmpDataX10Color,
                pointBackgroundColor: tmpDataX10Color,
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(220,220,220,1)",
                pointBorderWidth: 1,
                fill: true,
                data: tmpDataX10,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
        });

    }

    
    if ($("#chart_plot_02b").length) {
        var ctx = document.getElementById("chart_plot_02b");
        window.Chart1 = new Chart(ctx, {
            type: 'line',
            data: {
                labels: tmpXLabels,
                datasets: tmpDatasets
            },

            options: {
                scales: {
                    x: {
                        ticks: {
                            autoSkip: false,
                            // コールバック関数を使ってラベルの色を動的に変更
                            color: function(context) {
                                return sub201_setChartLabelColor(context);
                            }
                        }
                    },
                    y1: {
                        stacked: true,
                        type: 'linear',
                        position: 'left',
                        title:{
                            display: true,
                            text: '売上高'
                        }
                    }
                }
            }
        });
    }
}

// 以下、共通処理
function sub201_getChartMode(){
    var result = $('input[name="chart_mode"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}

function sub201_getRangeOption(){
    var result = $('input[name="range_option"]:checked');
    var chartOption = null
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartOption = result[i].value;
      }
    }
    return chartOption;
}

function sub201_getDetail2Option(){
    var result = $('input[name="detail2_option"]:checked');
    var chartOption = null
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartOption = result[i].value;
      }
    }
    return chartOption;
}

function sub201_setChartLabelColor(context){
    const label = context.tick.label;
    // ラベルが「特定の文字」を含む場合に赤色にする
    if (label.includes('㈷')) {
        return 'red';
    }
    if (label.includes('㈯')) {
        return 'blue';
    }
    if (label.includes('㈰')) {
        return 'red';
    }
    // それ以外はデフォルトの色
    return '#666';
}


$(document).ready(function() {
    initFor201();

});


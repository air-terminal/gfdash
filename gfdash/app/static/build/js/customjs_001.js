/*
    各画面専用javascript
    画面名：index.html
    ※命名規則　sub001_xxxxxx (パッケージ等の共通関数と重複させない為)
*/


function initFor001(){
    let initParam = {
        getMode:'init',
        getChartMode: sub001_getChartMode()
    };

    sub001_postView(initParam);
    sub001_syncChartWidth();
}


function sub001_postView(postParam){

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
        var chartResultsSum2 = [];
        var tmpSum = 0;

        var raijyoDetail = [];
        var raijyoDetailOld = [];
        var uriageDetail = [];
        var uriageDetailOld = [];

        var raijyoDetailSum = [];
        var raijyoDetailSumOld = [];
        var tmpRaijyoSum = 0;
        var tmpRaijyoSumOld = 0;

        var uriageDetailSum = [];
        var uriageDetailSumOld = [];
        var tmpUriageSum = 0;
        var tmpUriageSumOld = 0;

        var detailSum = {all:0, member:0, visitor:0, ave:0};
        var detailSumOld = {all:0, member:0, visitor:0, ave:0};
        var uriageSum = {all:0, ave:0};
        var uriageSumOld = {all:0, ave:0};

        var pDate = '';
        var tempDetail = {all:0, member:0, visitor:0, morning:0, noon:0, night:0};

        var chartXLabels = [];
        var chartDataNum = {raijyo:0, uriage:0};

        var chartTemp = [];
        var chartAveTemp = [];
        var chartXLabelsOption = [];
        var weatherData = [];
                                
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
                case 'raijyoDetail':
                    $.each(val, function(key2, val2) {
                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'business_day':
                                    pDate = val3.substr(5);
                                    break;
                                case 'all':
                                    tempDetail['all'] = val3;
                                    tmpRaijyoSum += parseInt(val3);
                                    break;
                            };
                        });
                        // グラフにプロットする際、取得したDB上は世界標準時なので日本時間に合わせる。
                        tmpSum = tmpSum + Number(tempDetail['all']);
                        raijyoDetail.push([pDate, tempDetail['all']]);
                        chartResultsSum2.push([pDate, tmpSum]);    
                        raijyoDetailSum.push([pDate, tmpRaijyoSum]);
                    });
                    break;
                case 'raijyoSum':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                detailSum['all'] = val2;
                                break;
                            case 'ave':
                                detailSum['ave'] = val2;
                                break;
                        };
                    });
                    break;
                case 'raijyoDetailOld':
                    $.each(val, function(key2, val2) {
                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'business_day':
                                    pDate = val3.substr(5);
                                    break;
                                case 'all':
                                    tempDetail['all'] = val3;
                                    tmpRaijyoSumOld += parseInt(val3);
                                    break;
                            };
                        });
                        raijyoDetailOld.push([pDate, tempDetail['all']]);
                        raijyoDetailSumOld.push([pDate, tmpRaijyoSumOld]);
                    });
                    break;
                case 'raijyoSumOld':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                detailSumOld['all'] = val2;
                                tmpRaijyoSumOld += val2;
                                break;
                            case 'ave':
                                detailSumOld['ave'] = val2;
                                break;
                        };
                    });
                    break;
                case 'uriageDetail':
                    $.each(val, function(key2, val2) {
                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'business_day':
                                    pDate = val3.substr(5);
                                    break;
                                case 'all':
                                    tempDetail['all'] = val3;
                                    tmpUriageSum += val3;
                                    break;
                            };
                        });
                        uriageDetail.push([pDate, tempDetail['all']]);
                        uriageDetailSum.push([pDate, tmpUriageSum]);
                    });
                    break;
                case 'uriageSum':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                uriageSum['all'] = val2;
                                break;
                            case 'ave':
                                uriageSum['ave'] = val2;
                                break;
                        };
                    });
                    break;
                case 'uriageDetailOld':
                    $.each(val, function(key2, val2) {
                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'business_day':
                                    pDate = val3.substr(5);
                                    break;
                                case 'all':
                                    tempDetail['all'] = val3;
                                    tmpUriageSumOld += val3;
                                    break;
                            };
                        });
                        uriageDetailOld.push([pDate, tempDetail['all']]);
                        uriageDetailSumOld.push([pDate, tmpUriageSumOld]);
                    });
                    break;
                case 'uriageSumOld':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                uriageSumOld['all'] = val2;
                                break;
                            case 'ave':
                                uriageSumOld['ave'] = val2;
                                break;
                        };
                    });
                    break;
                case 'weatherData':
                    $.each(val, function(key2, val2) {
                        tmpWeather = {temp:0,ave_temp:0,wind_speed:0,wind_direction:'',gaiyo:'',gaiyo_night:'', rainfall:0};

                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'weather_day':
                                    tmpDate = val3.substr(5);
                                    break;
                                case 'temp':
                                    tmpWeather['temp'] = val3;
                                    chartTemp.push([
                                        tmpDate, val3
                                    ]);
                                    break;
                                case 'ave_temp':
                                    tmpWeather['ave_temp'] = val3;
                                    chartAveTemp.push([
                                        tmpDate, val3
                                    ]);
                                    break;
                                case 'wind_speed':
                                    tmpWeather['wind_speed'] = val3;
                                    break;
                                case 'wind_direction':
                                    tmpWeather['wind_direction'] = val3;
                                    break;
                                case 'wind_instant_speed':
                                    tmpWeather['wind_instant_speed'] = val3;
                                    break;
                                case 'wind_instant_direction':
                                    tmpWeather['wind_instant_direction'] = val3;
                                    break;
                                case 'gaikyo':
                                    tmpWeather['gaikyo'] = val3;
                                    break;
                                case 'gaikyo_night':
                                    tmpWeather['gaikyo_night'] = val3;
                                    break;
                                case 'rainfall':
                                    tmpWeather['rainfall'] = val3;
                                    break;
                            };
                        });
                        weatherData.push([tmpWeather]);
                    });
                    break;

                case 'xLabel':
                    $.each(val, function(key2, val2) {
                        chartXLabels.push([
                            val2
                        ]);
                    });
                    break;
                case 'raijyoDataNum':
                    chartDataNum['raijyo'] = val;
                    break;
                case 'uriageDataNum':
                    chartDataNum['uriage'] = val;
                    break;
                case 'ta215_lastday':
                    $(".txt301").text(val);
                    break;
                case 'tb120_lastday':
                    $(".txt302").text(val);
                    break;
                case 'tz101_lastday':
                    $(".txt309").text(val);
                    break;
                case 'tz105_lastday':
                    $(".txt310").text(val);
                    break;
                case 'weather_station':
                    $(".txt320").text(val);
                    break;
                case 'amedas':
                    $(".txt321").text(val);
                    break;
                default:
                    break;
            }
        });
        // indexグラフ書き換え専用
        if(postParam.getChartMode === 'raijyo'){
            //来場者数
            sub001_set_chatjs_gf(chartXLabels, chartDataNum, raijyoDetail, raijyoDetailOld, raijyoDetailSum, raijyoDetailSumOld);
        } else {
            //売上高
            sub001_set_chatjs_gf(chartXLabels, chartDataNum, uriageDetail, uriageDetailOld, uriageDetailSum, uriageDetailSumOld);
        }
        $("#detail_option").hide();
        $("#temperature_option").hide();

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
        
            sub001_init_daterangepicker_single_call_gf();
        
            $('.input-group.date').datepicker('update', newDate);
            $("#gf_calendar").val(year + '年' + month + '月');
        
        } else {
            var newDate = new Date($("#calendar_initval").val());
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年' + month + '月');
        }

        // 前年比較値表示
        sub001_set_summaryData(detailSum, detailSumOld, uriageSum, uriageSumOld);

        // 天候情報表示
        com_set_day_weather_table(chartXLabels, weatherData);                

        $("#calendar_saveval").val($("#gf_calendar").val());
        sub001_set_btn();

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

function sub001_init_daterangepicker_single_call_gf() {

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
        
            sub001_postView(initParam);

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

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub001_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub001_postView(initParam);

    var newDate = new Date(initParam.getYM);
    var year = newDate.getFullYear().toString().padStart(4, '0');
    var month = (newDate.getMonth() + 1).toString();
    $("#gf_calendar").val(year + '年' + month + '月');
    $("#calendar_saveval").val($("#gf_calendar").val());

}

function btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub001_getChartMode()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub001_postView(initParam);

    var newDate = new Date(initParam.getYM);
    var year = newDate.getFullYear().toString().padStart(4, '0');
    var month = (newDate.getMonth() + 1).toString();
    $("#gf_calendar").val(year + '年' + month + '月');
    $("#calendar_saveval").val($("#gf_calendar").val());

}

function btnToggleChartMode(){
    // chart　来場者数／売上表示の切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub001_getChartMode()
    };

    sub001_postView(initParam);

}

function sub001_set_btn(){
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

function sub001_set_summaryData(detailSum, detailSumOld, uriageSum, uriageSumOld){

    var hikakuAll = detailSum['all'] - detailSumOld['all'];
    var hikakuAve = detailSum['ave'] - detailSumOld['ave'];
    var hikakuUriageAll = uriageSum['all'] - uriageSumOld['all'];
    var hikakuUriageAve = uriageSum['ave'] - uriageSumOld['ave'];

    // 合計来場者数
    $(".txt011").text(detailSum['all']);
    $(".txt011").attr('data-length',com_getTileCountTextLengthTag(detailSum['all']));
    $(".txt111").empty();
    $(".txt111").text(hikakuAll);
    if (hikakuAll > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt111");
        $(".txt111").wrapInner('<i class="green" />');
    } else if(hikakuAll < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt111");
        $(".txt111").wrapInner('<i class="red" />');
    }

    // 平均来場者数
    $(".txt012").text(detailSum['ave']);
    $(".txt012").attr('data-length',com_getTileCountTextLengthTag(detailSum['ave']));
    var tmpYoY = Math.round(hikakuAve * 100) / 100;
    $(".txt112").empty();
    $(".txt112").text(tmpYoY);
    if (tmpYoY > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt112");
        $(".txt112").wrapInner('<i class="green" />');
    } else if(tmpYoY < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt112");
        $(".txt112").wrapInner('<i class="red" />');
    }

    // 総売上
    $(".txt013").text(uriageSum['all'].toLocaleString());
    $(".txt013").attr('data-length',com_getTileCountTextLengthTag(uriageSum['all'].toLocaleString()));
    $(".txt113").empty();
    $(".txt113").text(hikakuUriageAll.toLocaleString());
    if (hikakuUriageAll > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt113");
        $(".txt113").wrapInner('<i class="green" />');
    } else if(hikakuUriageAll < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt113");
        $(".txt113").wrapInner('<i class="red" />');
    }

    // 平均売上額
    $(".txt014").text(uriageSum['ave'].toLocaleString());
    $(".txt014").attr('data-length',com_getTileCountTextLengthTag(uriageSum['ave'].toLocaleString()));
    var tmpYoY = Math.round(hikakuUriageAve * 100) / 100;
    $(".txt114").empty();
    $(".txt114").text(tmpYoY.toLocaleString());
    if (tmpYoY > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt114");
        $(".txt114").wrapInner('<i class="green" />');
    } else if(tmpYoY < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt114");
        $(".txt114").wrapInner('<i class="red" />');
    }

}


function sub001_set_chatjs_gf(chartXLabels, chartDataNum, chart_plotY1_data1, chart_plotY1_data2, chart_plotY2_data1, chart_plotY2_data2) {
    //値設定処理
    if (typeof(Chart) === 'undefined') {
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    if (!$("#chart_plot_02b").length) {
        return;
    }

    var data_len = $(chart_plotY1_data1).length - 1;
    if(data_len < 0){
        data_len = 0;
    }

    var tmpXLabels = [];
    var tmpData1 = [];
    var tmpData2 = [];
    var tmpData3 = [];
    var tmpData4 = [];
    var tmpDataNum = 0;

    var tmpDataLabel = "";

    // ラベルの設定
    if(sub001_getChartMode() === 'raijyo'){
        tmpDataLabel = "来場者数";
        tmpDataNum = chartDataNum['raijyo'];
    } else {
        tmpDataLabel = "売上高";
        tmpDataNum = chartDataNum['uriage'];
    }

    // Y軸ラベルのセット
    const yLabelElement = document.getElementById('chart_y_label');
    if (yLabelElement) {
        yLabelElement.innerText = (sub001_getChartMode() === 'raijyo') ? '来場者数' : '売上高(円)';
    }

    for (var key in chartXLabels) {
        tmpXLabels.push(chartXLabels[key][0]);
    };
    // 日付数＝データ数の場合は、区切り線位置を０にして表示させないようにする
    if(chartXLabels.length === chart_plotY1_data1.length){
        tmpDataNum = 0;
    }

    // Y1軸の設定1
    for (var key in chart_plotY1_data1) {
        tmpData1.push(chart_plotY1_data1[key][1]);
    };

    // Y1軸の設定2
    for (var key in chart_plotY1_data2) {
        tmpData2.push(chart_plotY1_data2[key][1]);
    };

    // Y2軸の設定1
    for (var key in chart_plotY2_data1) {
        tmpData3.push(chart_plotY2_data1[key][1]);
    };

    // Y2軸の設定2
    for (var key in chart_plotY2_data2) {
        tmpData4.push(chart_plotY2_data2[key][1]);
    };


    const shadowPlugin = {
      id: 'shadowPlugin',
      beforeDatasetsDraw(chart, args, options) {
        const { ctx } = chart;
        ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
        ctx.shadowBlur = 10;
        ctx.shadowOffsetX = 3;
        ctx.shadowOffsetY = 3;
      },
      afterDatasetsDraw(chart, args, options) {
        const { ctx } = chart;
        ctx.shadowBlur = 0;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;
      }
    };


    var ctx = document.getElementById("chart_plot_02b");
    window.Chart1 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tmpXLabels,
            datasets: [{
                order: 100,
                label: tmpDataLabel,
//                backgroundColor: "rgba(38, 185, 154, 1)",
                backgroundColor: "rgb(100, 203, 181)",
                fill: true,
                data: tmpData1,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
                ,categoryPercentage: 0.6
                ,barPercentage: 1.5
                ,lineAtIndex: tmpDataNum    // 独自プロパティ
            }, {
                order: 101,
                label: "前年" + tmpDataLabel,
                backgroundColor: "rgba(3, 88, 106, 0.7)",
                fill: true,
                data: tmpData2,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
                ,categoryPercentage: 0.6
                ,barPercentage: 1.5
            }, {
                order: 10,
                label: tmpDataLabel + "累計",
//                borderColor: "rgba(52,152,219,0.9)",
                borderColor: "rgb(252, 201, 149)",
                pointRadius: 2,
                borderWidth: 4,
                backgroundColor: "rgba(255, 255, 255, 1)",
                fill: false,
                data: tmpData3,
                yAxisID: 'y2'
            }, {
                order: 11,
                label: "前年" + tmpDataLabel + "累計",
                borderDash: [10, 5],
//                borderColor: "rgba(155,89,182,0.8)",
                borderColor: "rgb(230, 132, 110)",
                pointRadius: 2,
                borderWidth: 4,
                backgroundColor: "rgba(255, 255, 255, 1)",
                fill: false,
                data: tmpData4,
                yAxisID: 'y2'
            }]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false, // コンテナの高さに合わせるために必須            
            layout: {
                autoPadding: false,
                padding: {
                    left: 0,
                    right: 0,
                    top: 0,
                    bottom: 0
                }
            },
            scales: {
                x: {                    
                    ticks: {
                        display:false,
                        includeBounds: false, // 境界線のマージン計算を除外
                        autoSkip: false,
                        // コールバック関数を使ってラベルの色を動的に変更
                        color: function(context) {
                            return com_setChartLabelColor(context);
                        }
                    },
                    grid: {
                        offset: true, // 棒グラフとグリッドの中心を合わせる
                        drawTicks: false,
                    },
                    afterFit: function(axis) {
                        axis.paddingRight = 0; // 右側の余白をゼロに固定
                    },
                },
                y1: {
                    type: 'linear',
                    position: 'left',
                    afterFit: function(axis) {
                        axis.width = 80;
                    },
                    title:{
                        display: false,
                        text: tmpDataLabel
                    }
                    
                },
                y2: {
                    display: false,
                    afterFit: function(axis) {
                        axis.width = 0; // 右側は不要なら0に
                        axis.paddingRight = 0;
                    },
                }
            }
        },
        plugins: [verticalLinePlugin, shadowPlugin]   // プラグインを登録
    });
}

// 以下、共通処理
function sub001_getChartMode(){
    var result = $('input[name="chart_mode"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}

function sub001_syncChartWidth() {
    const tableContainer = document.getElementById('weather_table_container');
    const chartWrapper = document.getElementById('chart_wrapper'); // 親divを指定
    const chartCanvas = document.getElementById('chart_plot_02b');
    
    if (!tableContainer || !chartWrapper || !chartCanvas) return;

    const ro = new ResizeObserver(entries => {
        // テーブル本体の幅を取得
        const tableElement = tableContainer.querySelector('table');
        if (tableElement) {
            const targetWidth = tableElement.offsetWidth;
            
            // 現在の幅と異なる場合のみ実行（無限ループ防止の二重策）
            if (chartWrapper.style.width !== targetWidth + 'px') {
                chartWrapper.style.width = targetWidth + 'px';
                
                // Chart.jsにリサイズを通知
                if (window.Chart1) {
                    window.Chart1.resize();
                }
            }
        }
    });

    // テーブルのコンテナを監視
    ro.observe(tableContainer);
}

$(document).ready(function() {
    initFor001();
});


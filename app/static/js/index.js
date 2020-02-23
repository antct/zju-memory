let animation = {};

animation.initAnimationItems = () => {
    $('.animated').each(function () {
        var aniDuration, aniDelay;

        $(this).attr('data-origin-class', $(this).attr('class'));

        aniDuration = $(this).data('ani-duration');
        aniDelay = $(this).data('ani-delay');

        $(this).css({
            'visibility': 'hidden',
            'animation-duration': aniDuration,
            '-webkit-animation-duration': aniDuration,
            'animation-delay': aniDelay,
            '-webkit-animation-delay': aniDelay
        });
    });
};

animation.playAnimation = (swiper) => {
    animation.clearAnimation();

    var aniItems = swiper.slides[swiper.activeIndex].querySelectorAll('.animated');

    $(aniItems).each(function () {
        var aniName;
        $(this).css({ 'visibility': 'visible' });
        aniName = $(this).data('ani-name');
        $(this).addClass(aniName);
    });
};

animation.clearAnimation = () => {
    $('.animated').each(function () {
        $(this).css({ 'visibility': 'hidden' });
        $(this).attr('class', $(this).data('origin-class'));
    });
}

let app = {};

app.init = function () {
    let sportIndex = 4;
    let endIndex = 6;
    let type = store.get('data')['basic']['type'];

    if (type === 'grs') {
        $(".sport-page")[0].remove();
        app.initWelcome();
        app.initEcard();
        app.initJwbinfosys();
        app.initLibrary();
        app.initCC98();
        sportIndex = -1;
        endIndex = 5;
    } else {
        app.initWelcome();
        app.initEcard();
        app.initJwbinfosys();
        app.initLibrary();
        app.initCC98();
    }

    $('#root-container').hide();
    $('#swiper-container').show();

    new Swiper('#swiper-container', {
        effect: 'coverflow',
        speed: 400,
        direction: 'vertical',
        fadeEffect: {
            crossFade: false
        },
        coverflowEffect: {
            rotate: 100,
            stretch: 0,
            depth: 300,
            modifier: 1,
            slideShadows: false
        },
        flipEffect: {
            limitRotation: true,
            slideShadows: false
        },
        on: {
            init: function () {
                animation.initAnimationItems();
                animation.playAnimation(this);
            },
            touchMove: (event) => {
                $(".arrow").hide();
            },
            touchStart: (event) => {
            },
            transitionStart: function () {
                $(".arrow").hide();
            },
            transitionEnd: function () {
                if (this.activeIndex != endIndex) {
                    $(".arrow").show();
                }
                if (sportIndex !== -1 && this.activeIndex == sportIndex) {
                    app.initSport();
                }
                animation.playAnimation(this);
            }
        },
    });
    $('.music').on('click', function () {
        $(this).toggleClass('play');
        let audio = document.getElementById('audio');
        if (audio.paused) {
            audio.play();
        } else {
            audio.pause();
        }
    });
    $("#audio").bind('ended', function () {
        $(this).parent().removeClass('play');
    });
};

app.initWelcome = () => {
    try {
        let data = store.get('data')['basic'];
        let options = {
            strings: [
                "Hi，" + data['name'] + "。\n" +
                "你好呀！\n" +
                "这是你在浙大的，\n" +
                "第" + data['date'] + "天。\n" +
                "不知道在你的记忆里，\n" +
                "是否会有这样一个园子。\n" +
                "在这里，\n" +
                "你会走过四年，\n" +
                "十六个季节。\n\n" +
                "即将别离的时候，\n" +
                "我想为你，\n" +
                "画下这记忆里的园子。\n" +
                "我的画笔，\n" +
                "是数字，\n" +
                "画的名字，\n" +
                "叫浙大记忆。\n\n" +
                "二零一九年三月于求是园。"
            ],
            startDelay: 500,
            typeSpeed: 100,
            backSpeed: 50
        }
        new Typed("#typed", options);
    } catch (e) {
    }
}

app.initEcard = () => {
    try {
        data = store.get('data')['ecard'];

        $("#ecard-merc-count").html(data['merc_count'].toFixed(0));
        $("#ecard-day-count").html(data['day_span'].toFixed(0));

        $("#ecard-alipay").html(data['alipay'].toFixed(0));
        $("#ecard-shower").html(data['shower']);
        $("#ecard-market").html(data['market']);
        $("#ecard-normal").html(data['normal']);
        $("#ecard-bank").html(data['bank']);

        $("#ecard-most-merc-1-mercname").html(data['most_merc'][0]['mercname']);
        $("#ecard-most-merc-2-mercname").html(data['most_merc'][1]['mercname']);
        $("#ecard-most-merc-3-mercname").html(data['most_merc'][2]['mercname']);
        $("#ecard-most-merc-1-count").html(data['most_merc'][0]['count']);

        $("#ecard-most-tranamt-place").html(data['most_tranamt']['occtime'] + " " + data['most_tranamt']['mercname']);
        $("#ecard-most-tranamt-count").html(data['most_tranamt']['tranamt'].toFixed(2));

        $("#ecard-normal-avg").html((data['normal'] / data['day_count']).toFixed(2));

        $("#ecard-most-day-occtime").html(data['most_day']['occtime']);
        $("#ecard-most-day-tranamt").html(data['most_day']['tranamt'].toFixed(2));

        let most_dining_mercname = "";
        let most_dining_count = 0;
        for (let i in data['most_dining']) {
            most_dining_mercname += data['most_dining'][i]['mercname'];
            most_dining_mercname += " ";
            most_dining_count += data['most_dining'][i]['count'];
        }
        $("#ecard-most-dining-mercname").html(most_dining_mercname);
        $("#ecard-most-dining-count").html(most_dining_count);
    } catch (e) {
        return
    }
}

app.initJwbinfosys = () => {
    try {
        let data = store.get('data')['jwbinfosys'];

        if (data['code'] === 1) {
            $("#course-error-text").html("抱歉啦！ 毕业了这部分暂时就看不到了~")
            $('#course-normal').hide();
            $("#course-error").show();
            return
        }

        if (data['code'] === 2) {
            $("#course-error-text").html("教务网课程评价窗口拦截 请评价后再试~")
            $('#course-normal').hide();
            $("#course-error").show();
            return
        }

        $("#course-total-count").html(data['total_count']);
        $("#course-major-count").html(data['major_count']);
        $("#course-total-credit").html(data['total_credit']);
        $("#course-semester-first").html(data['semester']['first']);
        $("#course-semester-last").html(data['semester']['last']);

        let course_highest_course = '';
        for (let i in data['score']) {
            course_highest_course += data['score'][i]['name'];
            course_highest_course += " ";
            if (parseInt(i) != data['score'].length - 1 && !((parseInt(i) + 1) % 2)) {
                course_highest_course += "\n";
            }
        }
        $("#course-highest-course").html(course_highest_course);

        $("#course-teacher-name").html(data['teacher']['name']);
        $("#course-teacher-count").html(data['teacher']['count']);
        $("#course-teacher-total-count").html(data['teacher']['total_count']);

        let course_teacher_course = '';
        for (let i in data['teacher']['course']) {
            course_teacher_course += data['teacher']['course'][i];
            course_teacher_course += " ";
            if (parseInt(i) != data['teacher']['course'].length - 1 && !((parseInt(i) + 1) % 2)) {
                course_teacher_course += "\n";
            }
        }
        $("#course-teacher-course").html(course_teacher_course);
        $("#course-semester-name").html(data['semester']['name']);
        $("#course-semester-count").html(data['semester']['count']);
        $("#course-semester-avg").html(data['semester']['avg']);

        $("#course-first-name").html(data['first_course']['name']);
        $("#course-first-teacher").html(data['first_course']['teacher']);
        $("#course-first-place").html(data['first_course']['place']);
    } catch (e) {
        return
    }
}

app.initSport = () => {
    let option = {
        title: {
            show: true,
            text: '浙江大学养猪场指定体重计',
            x: 'center',
            y: 'bottom',
        },
        legend: {
            data: ['身高', 'BMI', '体重'],
            textStyle: {
                color: '#414141',
                fontStyle: 'normal',
                fontWeight: 'bold',
            }
        },
        xAxis: [
            {
                type: 'category',
                data: []
            }
        ],
        yAxis: [
            {
                type: 'value',
                show: false,
                scale: true
            },
            {
                type: 'value',
                show: false,
                scale: false
            },
            {
                type: 'value',
                show: false,
                scale: true
            }
        ],
        series: [
            {
                name: '身高',
                type: 'line',
                clickable: false,
                data: [],
                yAxisIndex: 0,
                itemStyle: {
                    normal: {
                        label: {
                            show: true,
                            position: 'right',
                        }
                    }
                },
                animationDelay: function (idx) {
                    return idx * 10;
                }
            },
            {
                name: 'BMI',
                type: 'scatter',
                clickable: false,
                data: [],
                yAxisIndex: 1,
                itemStyle: {
                    normal: {
                        label: {
                            show: true,
                            position: 'left',
                        }
                    }

                },
                animationDelay: function (idx) {
                    return idx * 10;
                }
            },
            {
                name: '体重',
                type: 'bar',
                clickable: false,
                data: [],
                yAxisIndex: 2,
                itemStyle: {
                    normal: {
                        label: {
                            show: true,
                            position: 'top',
                        }
                    }

                },
                animationDelay: function (idx) {
                    return idx * 10;
                }
            },

        ],
        animationEasing: 'elasticOut',
        animationDelayUpdate: function (idx) {
            return idx * 1000;
        }
    };
    try {
        data = store.get('data')['sport']

        let myChart = echarts.init(document.getElementById('basic'));

        option['xAxis'][0]['data'] = data['year']
        option['series'][0]['data'] = data['height'];
        option['series'][1]['data'] = data['bmi'];
        option['series'][2]['data'] = data['weight'];

        myChart.setOption(option);
        myChart.resize();

        $("#sport-score").html(data['score']);

        $("#sport-run").html(data['run']);

        $("#sport-best-score").html(data['best']['score']);
        $("#sport-best-name").html(data['best']['name']);

        $("#sport-worst-score").html(data['worst']['score']);
        $("#sport-worst-name").html(data['worst']['name']);
    } catch (e) {
        return
    }
}

app.initLibrary = () => {
    try {
        data = store.get('data')['library'];
        if (data['code'] === 0) {
            $("#library-first-book-date").html(data['first_book']['date']);
            $("#library-first-book-author").html(data['first_book']['author']);
            $("#library-first-book-name").html(data['first_book']['name']);

            $("#library-last-book-date").html(data['last_book']['date']);
            $("#library-last-book-author").html(data['last_book']['author']);
            $("#library-last-book-name").html(data['last_book']['name']);

            $("#library-early-book-year").html(data['early_book']['year']);
            $("#library-early-book-author").html(data['early_book']['author']);
            $("#library-early-book-name").html(data['early_book']['name']);

            $("#library-long-book-day").html(data['long_book']['day']);
            $("#library-long-book-author").html(data['long_book']['author']);
            $("#library-long-book-name").html(data['long_book']['name']);

            $("#library-most-page-author").html(data['most_page']['author']);
            $("#library-most-page-name").html(data['most_page']['name']);
            // $("#library-most-page-page").html(data['most_page']['page']);

            $("#library-total-count").html(data['count']);

            $("#library-author-name").html(data['most_author']['name']);
            $("#library-author-count").html(data['most_author']['count']);

            $("#library-place-count").html(data['most_place']['count']);
            $("#library-place-name").html(data['most_place']['name']);


            let topic = "";
            for (let i in data['topic']['label']) {
                topic += " ";
                topic += data['topic']['label'][i];
            }
            $("#library-topic-label").html(topic);
            $("#library-topic-count").html(data['topic']['count']);
        }
        else {
            $("#library-normal").hide();
            $("#library-none").show();
            if (data['code'] === -1) {
                $("#library-none-comment1").html("图书馆网站暂时奔溃了~");
                $("#library-none-comment2").html("让网站休息一下吧。<br/>稍后重新登陆试试哦！");
            }
            if (data['code'] === 1) {
                $("#library-none-comment1").html("暂时没有查询到你的借阅记录哦~");
                $("#library-none-comment2").html("毕业前去图书馆逛逛吧。<br/>达成借阅图书成就！");
            }
            if (data['code'] === 2) {
                $("#library-none-comment1").html("可能是修改密码窗口拦截了请求哦~");
                $("#library-none-comment2").html("到 http://webpac.zju.edu.cn/zjusso</a><br/>修改一下密码之后再尝试把！");
            }
        }
    } catch (e) {
        return
    }
}

app.initCC98 = () => {
    try {
        data = store.get('data')['cc98'];
        gender = store.get('data')['basic']['gender'];

        if (gender === 'boy') {
            $("#cc98-avatar").attr('src', 'static/images/cc98_boy.png');
            $("#sport-run-comment").html('还是当年那个追风少年吗?')
        }
        else {
            $("#cc98-avatar").attr('src', 'static/images/cc98_gril.png');
            $("#sport-run-comment").html('还是当年那个追风少女吗?')
        }

        if (data['code'] === 0 || data['code'] === 1) {
            $("#cc98-count").html(data['count']);
            $("#cc98-login-times").html(data['login_times']);
            $("#cc98-comment-times").html(data['comment_times']);
            $("#cc98-follow-count").html(data['follow_count']);
            $("#cc98-fan-count").html(data['fan_count']);
            $("#cc98-register-time").html(data['register_time']);
            $("#cc98-post-count").html(data['post_count']);
            $("#cc98-like-count").html(data['like_count']);
            $("#cc98-pop-count").html(data['pop_count']);

            if (data['code'] === 0) {
                $("#cc98-first-topic-time").html(data['first_topic']['time']);
                $("#cc98-first-topic-title").html(data['first_topic']['title']);
                $("#cc98-post-most-board").html(data['post_most']['board']);
                $("#cc98-post-most-count").html(data['post_most']['count']);
            } else {
                $("#cc98-post-yes").hide();
                $("#cc98-post-no").show();
            }

            if (data['count'] > 1) {
                $("#cc98-comment1").html("多面");
            } else {
                $("#cc98-comment1").html("简单");
            }
            if (data['comment_times'] > 100) {
                $("#cc98-comment2").html("经常冒泡");
            } else {
                $("#cc98-comment2").html("习惯潜水");
            }
        } else if (data['code'] === 2) {
            $("#cc98-post-yes").hide();
            $("#cc98-post-no").hide();
            // $("#cc98-normal").hide();
            $("#cc98-none").show();
        } else {

        }
    } catch (e) {
        return
    }
}

$(document).ready(function () {
    app.init();
});

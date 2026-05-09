let csrfmiddlewaretoken = "";
const csrfInput = document.getElementsByName("csrfmiddlewaretoken")[0];
if (csrfInput && csrfInput.value) {
    csrfmiddlewaretoken = csrfInput.value;
}

(function (global) {
    function sfFillButtonLoading(btn, busyText) {
        if (!btn || btn.tagName !== "BUTTON") return;
        if (!btn.dataset.sfOrigHtml) btn.dataset.sfOrigHtml = btn.innerHTML;
        btn.disabled = true;
        btn.setAttribute("aria-busy", "true");
        btn.classList.add("sf-is-loading");
        btn.textContent = "";
        var sp = document.createElement("span");
        sp.className = "sf-btn-spinner";
        sp.setAttribute("aria-hidden", "true");
        var lab = document.createElement("span");
        lab.className = "sf-btn-busy-text";
        lab.textContent = busyText || "…";
        btn.appendChild(sp);
        btn.appendChild(lab);
    }
    function sfClearButtonLoading(btn) {
        if (!btn || btn.tagName !== "BUTTON") return;
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
        btn.classList.remove("sf-is-loading");
        if (btn.dataset.sfOrigHtml != null) {
            btn.innerHTML = btn.dataset.sfOrigHtml;
            delete btn.dataset.sfOrigHtml;
        }
    }
    global.sfFillButtonLoading = sfFillButtonLoading;
    global.sfClearButtonLoading = sfClearButtonLoading;
})(typeof window !== "undefined" ? window : this);

$('#register-form').submit(function (e) {
    e.preventDefault();
    var formEl = this;
    var btn = formEl.querySelector('button[type="submit"]');
    var busy = formEl.getAttribute('data-sf-busy-label') || '…';
    sfFillButtonLoading(btn, busy);

    $.ajaxSetup({
        headers: {
            'X-CSRFToken': csrfmiddlewaretoken
        }
    });

    let form = $(this);

    $.ajax({
        type: 'POST',
        url: form.attr('action'),
        data: form.serialize(),
        dataType: 'json',
        success: function (res) {
            if (res.status === false) {
                sfClearButtonLoading(btn);
                $('#register-error').text('');
                $.each(res.errors, (index, item) => {
                    $('#register-error').append(item + '<br/>');
                });
            }
            if (res.status === true) {
                $('#register-error').text(res.message);
                formEl.reset();
                sfClearButtonLoading(btn);
                setTimeout(function () {
                    $("#register").modal("hide");
                    $("#login").modal("show");
                }, 2000);
            }
        },
        error: function (err) {
            sfClearButtonLoading(btn);
            console.log(err);
        }
    });
});


$('#login-form').submit(function (e) {
    e.preventDefault();
    var formEl = this;
    var btn = formEl.querySelector('button[type="submit"]');
    var busy = formEl.getAttribute('data-sf-busy-label') || '…';
    sfFillButtonLoading(btn, busy);

    $.ajaxSetup({
        headers: {
            'X-CSRFToken': csrfmiddlewaretoken
        }
    });

    let form = $(this);

    $.ajax({
        type: 'POST',
        url: form.attr('action'),
        data: form.serialize(),
        dataType: 'json',
        success: function (res) {
            if (res.status === false) {
                sfClearButtonLoading(btn);
                $('#login-error').text('');
                $.each(res.errors, (index, item) => {
                    $('#login-error').append(item + '<br/>');
                });
            } else if (res.status === true) {
                $('#login-error').text(res.message);
                formEl.reset();
                setTimeout(function () {
                    location.reload();
                }, 2000);
            }
        },
        error: function (err) {
            sfClearButtonLoading(btn);
            console.log(err);
        }
    });
});

$(document).ready(function () {
    // Sidebar fallback controls (keeps mobile sidebar usable if bundled handler fails)
    var $body = $('body');
    var $sidebarBackdrop = $('.sidebar-backdrop');

    // Drop bundled header search dropdown (TRACK / View all); search still submits via the form GET.
    $('#searchForm').off('click');
    $body.removeClass('open-search');
    $('.header-backdrop').removeClass('show');

    function openSidebar() {
        $body.addClass('open-sidebar');
        $sidebarBackdrop.addClass('show');
    }

    function closeSidebar() {
        $body.removeClass('open-sidebar');
        $sidebarBackdrop.removeClass('show');
    }

    $('#openSidebar').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openSidebar();
    });

    $('#hideSidebar').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        closeSidebar();
    });

    $('#toggleSidebar').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        $body.toggleClass('iconic-sidebar');
    });

    $sidebarBackdrop.on('click', closeSidebar);

    // Tap outside the drawer (main column / header) closes the menu on mobile.
    $(document).on('click', '#wrapper', function (e) {
        if (!$body.hasClass('open-sidebar')) return;
        if ($(e.target).closest('#sidebar').length) return;
        if ($(e.target).closest('#openSidebar').length) return;
        closeSidebar();
    });

    // Mobile hard-fallback: ensure sidebar links always navigate on tap.
    $(document).on('touchstart click', '#sidebar .nav-link', function (e) {
        var href = $(this).attr('href');
        if (!href || href === '#') return;
        e.preventDefault();
        e.stopPropagation();
        window.location.href = href;
    });

    $('#songFile').on('change', function (e) {
        if ($(this).val().split("\\")[2]) {
            $('#songName').val($(this).val().split("\\")[2]);
            $('#songChoose').text($(this).val().split("\\")[2]);
        }
    });

    $('#audioPlayer').css('visibility', 'hidden');

    $('input[type=radio][name=type]').change(function () {
        if (this.value === 'free') {
            $('#price').find("*").prop('disabled', true);
        } else if (this.value === 'paid') {
            $('#price').find("*").prop('disabled', false);
        }
    });

    // tag-it plugin
    $("#song_tag").tagit();

    // search
    $('#search').on('keyup', function () {
        let keyword = $(this).val();
        if (keyword !== '') {
            $.ajax({
                type: 'GET',
                url: $(this).data('search-url') + '?q=' + keyword,
                dataType: 'json',
                success: function (res) {
                    let search_track = $('#search-track');
                    search_track.empty();
                    if (res.songs.length > 0) {
                        $.each(res.songs, function (index, song) {
                            let artists = "";
                            $.each(song.artists, function (i, artist) {
                                if (i !== 0) artists += ", " + artist.name;
                                else artists += artist.name;
                            });
                            search_track.append('<div class="col-xl-4 col-md-6 col-12">\n' +
                                '                            <div class="custom-card mb-3">\n' +
                                '                                <a href="/track/' + song.audio_id + '" class="text-dark custom-card--inline">\n' +
                                '                                    <div class="custom-card--inline-img">\n' +
                                '                                        <img src="' + song.thumbnail + '" alt=""\n' +
                                '                                             class="card-img--radius-sm">\n' +
                                '                                    </div>\n' +
                                '                                    <div class="custom-card--inline-desc">\n' +
                                '                                        <p class="text-truncate mb-0">' + song.title + '</p>\n' +
                                '                                        <p class="text-truncate text-muted font-sm">' + artists + '</p>\n' +
                                '                                    </div>\n' +
                                '                                </a>\n' +
                                '                            </div>\n' +
                                '                        </div>')
                        });
                    } else {
                        search_track.append('<div class="col-xl-4 col-md-6 col-12"><p>Nothing found with this keyword!</p></div>')
                    }
                },
                error: function (err) {
                    console.log(err);
                }
            });
        }
    });
});

(function () {
    function sfRestoreFormAfterBfcache(form) {
        form.querySelectorAll('button[type="submit"]').forEach(function (btn) {
            if (typeof window.sfClearButtonLoading === 'function') {
                window.sfClearButtonLoading(btn);
            }
        });
        form.querySelectorAll('input[type="submit"]').forEach(function (inp) {
            if (inp.dataset.sfOrigValue != null) {
                inp.value = inp.dataset.sfOrigValue;
                delete inp.dataset.sfOrigValue;
            }
            inp.disabled = false;
        });
        delete form.dataset.sfSubmitInFlight;
    }

    function sfMarkFormSubmitting(form) {
        var busy = form.getAttribute('data-sf-busy-label') || '…';
        form.dataset.sfSubmitInFlight = '1';
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (btn) {
            if (btn.tagName === 'BUTTON' && typeof window.sfFillButtonLoading === 'function') {
                window.sfFillButtonLoading(btn, busy);
            } else if (btn.tagName === 'INPUT') {
                if (!btn.dataset.sfOrigValue) btn.dataset.sfOrigValue = btn.value;
                btn.disabled = true;
                btn.value = busy;
            }
        });
    }

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (form.classList.contains('sf-no-submit-state')) return;
        if (!form.classList.contains('sf-submit-state')) return;
        if (form.dataset.sfSubmitInFlight === '1') {
            e.preventDefault();
            return;
        }
        form.dataset.sfSubmitInFlight = '1';
        // Defer disabling submit buttons until after the default form-submit action has
        // built the entry list. Synchronously disabling in this handler drops the
        // submitter's name/value (e.g. action=approve_vote_requests), breaking POST handlers.
        window.setTimeout(function () {
            sfMarkFormSubmitting(form);
        }, 0);
    }, false);

    window.addEventListener('pageshow', function (ev) {
        if (!ev.persisted) return;
        document.querySelectorAll('form.sf-submit-state').forEach(sfRestoreFormAfterBfcache);
    });
})();

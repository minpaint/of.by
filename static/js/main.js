/* Охрана труда — main.js */

document.addEventListener('DOMContentLoaded', function () {

  // Авто-закрытие мобильного меню при клике на пункт
  document.querySelectorAll('.nav-item').forEach(function (link) {
    link.addEventListener('click', function () {
      var nav = document.querySelector('.main-nav');
      if (nav) nav.classList.remove('nav-open');
    });
  });

  // Подсветка активного пункта меню
  var path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(function (link) {
    var href = link.getAttribute('href');
    if (href && href !== '/' && path.startsWith(href)) {
      link.classList.add('active');
    }
  });

});

/**
 * DarkEye 产品宣传页 — 滚动渐显与交互
 */
(function () {
  'use strict';

  function revealOnScroll() {
    var reveals = document.querySelectorAll('.reveal');
    if (!reveals.length) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px'
      }
    );

    reveals.forEach(function (el) {
      observer.observe(el);
    });
  }

  function initHeroReveal() {
    var heroContent = document.querySelector('.hero-content');
    if (!heroContent) return;

    var children = heroContent.querySelectorAll('.reveal');
    children.forEach(function (el, i) {
      el.style.transitionDelay = (i * 0.1) + 's';
      el.classList.add('revealed');
    });
  }

  function init() {
    initHeroReveal();
    revealOnScroll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

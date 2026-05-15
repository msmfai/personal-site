---
layout: about
title: About
permalink: /
subtitle: AI research scientist with a chronic habit of cross-disciplinary work

profile:
  align: right
  image: prof_pic.jpg
  image_circular: false # crops the image to make it circular
  more_info:

selected_papers: true # includes a list of papers marked as "selected={true}"
social: true # includes social icons at the bottom of the page

announcements:
  enabled: false # includes a list of news items
  scrollable: true # adds a vertical scroll bar if there are more than 3 news items
  limit: 5 # leave blank to include all the news in the `_news` folder

latest_posts:
  enabled: false
  scrollable: true # adds a vertical scroll bar if there are more than 3 new posts items
  limit: 3 # leave blank to include all the blog posts

timeline:
  enabled: true
  scrollable: true # adds a vertical scroll bar
  limit: # number of timeline items to show
---

I'm Marin, and I'm one of those people who can't stop noticing when the same idea shows up in completely different fields. I do AI research; right now most of my time goes into two threads.

At **Electronic Arts SEED**, I work on real-time generative AI for AAA games. The fun question is how to fit a neural network into a production frame-time budget when standard architectures are an order of magnitude too expensive. Lots of CUDA. Lots of structure to exploit.

{% if site.show_consultancy %}Through **Solomonoff Consultancy**, I design evaluation frameworks for scientific reasoning in frontier AI models. The fun question there is the kind of correctness that doesn't reduce to a unit test: did the model actually learn to do chemistry, or did it just memorize the answer key? Coordinating a hundred-plus domain experts to find out is more fun than it has any right to be. Open to select engagements; get in touch to discuss fit.{% endif %}

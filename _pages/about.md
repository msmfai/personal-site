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

I'm Marin. I do AI research, mostly at the intersection of fields that don't usually talk to each other. Right now most of my time goes into two threads.

At **Electronic Arts SEED**, I work on real-time generative AI for AAA games. The problem is fitting neural networks into a shipping game engine's frame-time budget: a lot of CUDA, a lot of structure to exploit.

{% if site.show_consultancy %}Through **Solomonoff Consultancy**, I design evaluation frameworks for scientific reasoning in frontier AI models. The question is the kind of correctness that doesn't reduce to a unit test: did the model actually learn to do chemistry, or did it just memorize the answer key? Most of the work is coordinating expert teams to construct evaluations that genuinely test for understanding. Open to select engagements; get in touch to discuss fit.{% endif %}

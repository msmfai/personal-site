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

I'm Marin. I do AI research, mostly at the intersection of fields that don't usually talk to each other. These days I split my time between two things.

At **Electronic Arts SEED**, I work on real-time generative AI for AAA games. Fitting neural networks into a shipping game engine's frame-time budget involves a lot of CUDA work and a fair amount of finding structure in the problem that you can take advantage of.

{% if site.show_consultancy %}Through **Solomonoff Consultancy**, I design evaluation frameworks for scientific reasoning in frontier AI models. The hard question is what good evaluation looks like when correctness can't be reduced to a unit test. Did the model actually learn to do chemistry, or did it just memorize the answer key? Most of the work involves coordinating expert teams to construct evaluations that genuinely test for understanding. Open to select engagements, so get in touch if it sounds like a fit.{% endif %}

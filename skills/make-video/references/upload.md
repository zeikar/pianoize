# Writing upload.md

`upload.md` is what the user pastes into YouTube Studio for one video. English is the video's default language; Korean is its translation, which the user adds under Languages, so a Korean viewer sees the Korean title and description. Every field the user copies sits in its own `text` code block, so it copies without stray Markdown.

## The title

- **English:** `<the song's name> - <the work> OST | Piano Arrangement`, or for a song from an album or an artist, `<the song's name> - <the artist> | Piano Arrangement`. Add the song's other name in parentheses where it has two: a place's name and its theme's name, say.
- **Korean:** the same shape, with the Korean names where the work has them and `피아노` for "Piano Arrangement": the user found `피아노 편곡` stiff in a title.
- At most 100 characters, YouTube's limit. Leave out "Synthesia" and other words for the video's style: the user dropped them.

## The description

- **The credits**, a line each, as the rules in SKILL.md set out:
  - the music: the song, its composer where it is sourced, and the work with its rights holder (`© <holder>`);
  - the arrangement's source: "Arrangement based on tsumugi-piano-cover (CC BY-NC 4.0)" for an arrangement from the cover, or "Transcription: tsumugi (MIT)" for one from the transcription alone;
  - "Arranged with pianoize: https://github.com/zeikar/pianoize";
  - the SoundFont's credit line.
- **The hashtags,** after a blank line: three or four. YouTube shows the first three above the title, so the work comes first, then `#Piano` and `#PianoArrangement`.
- **Korean:** translate the labels (음악, 작곡, 편곡, 채보, 피아노 음원) and keep every name, license and URL as it is. Its hashtags may swap one for the work's Korean name.

## The tags

One list for both languages, comma-separated, at most 500 characters with the commas, YouTube's limit. The specific first: the song's names, the work's names in both languages, a common Korean nickname for its music where there is one. Then the general: piano, piano arrangement, piano cover, falling notes, 피아노, 피아노 편곡, and the genre, such as game music and 게임 음악.

## The settings

- **Monetization:** off for an arrangement from the cover. For one from the transcription alone, the arrangement adds no terms, so the song's rights and any fan-work guidelines decide: say so, and leave it to the user.
- **Category:** Music.
- **Audience:** not made for kids.
- **Languages:** the title and description language is English; add Korean under Languages and paste the Korean title and description there.
- **Thumbnail:** `arranged.jpg`.
- **To confirm:** every credit marked unconfirmed, with where it was found.

## Its shape

````markdown
# A Made-up Song: upload

## Files

- Video: `arranged.mp4`
- Thumbnail: `arranged.jpg`

## English (default)

Title:

```text
A Made-up Song - A Made-up Game OST | Piano Arrangement
```

Description:

```text
Music: A Made-up Song (composed by Someone), A Made-up Game © A Made-up Studio
Transcription: tsumugi (MIT)
Arranged with pianoize: https://github.com/zeikar/pianoize
Piano sound: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0), via FreePats

#MadeUpGame #Piano #PianoArrangement
```

## 한국어 (Korean, under Languages)

제목:

```text
메이드업 송 - 메이드업 게임 OST | 피아노
```

설명:

```text
음악: A Made-up Song (작곡: Someone), A Made-up Game © A Made-up Studio
채보: tsumugi (MIT)
편곡 도구: pianoize https://github.com/zeikar/pianoize
피아노 음원: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0), via FreePats

#메이드업게임 #Piano #PianoArrangement
```

## Tags

```text
A Made-up Song, A Made-up Game, A Made-up Game OST, 메이드업 게임, piano, piano arrangement, piano cover, falling notes, game music, 피아노, 피아노 편곡, 게임 음악
```

## Settings

- Monetization: the arrangement adds no terms; the song's rights decide.
- Category: Music
- Audience: not made for kids
- Languages: English; add Korean and paste the Korean title and description.
- Thumbnail: `arranged.jpg`
- To confirm: the composer credit, found only on a fan wiki.
````

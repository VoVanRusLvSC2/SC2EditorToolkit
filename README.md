# SC2 Native Toolkit

Приватный модульный backend оригинального StarCraft II Editor для VoVanRusLvSC2.
Редактор работает на отдельном невидимом рабочем столе Windows. Физический ввод
мыши/клавиатуры и переключение рабочего стола не используются.

## Возможности

| Модуль | Возможности |
|---|---|
| Editor | Автоматический скрытый запуск, открытие копий `.SC2Map`/`.SC2Mod`, чтение диагностик |
| Triggers | Оригинальный `Triggers XML → Galaxy`, штатная компиляция текущих триггеров |
| Galaxy | Побайтный экспорт `.galaxy`, SHA-256, скачивание через API, защита от перезаписи |
| Render | PNG следующего кадра из D3D9 backbuffer; пиксели рабочего стола не читаются |
| Cutscene | Загрузка `.SC2Cutscene`, камера, таймкод, PNG и MP4 всей сцены или диапазона |
| MCP | Отдельный stdio EXE, инструменты редактора/экспорта/диагностик/рендера |

Генератор и компилятор — **оригинальные**, работающие внутри установленного Editor.
Собственного Galaxy-генератора здесь нет. Внутренние GUI-окна существуют только
на приватном desktop; техническое окно графического потока невидимо.

## Границы рендера

Кадр берётся непосредственно перед `Present`, при необходимости с resolve MSAA,
копированием render target в system memory и PNG-кодированием через Windows WIC.
Захват привязан к HWND основного viewport катсцены. Посторонние буферы,
включая чёрный служебный буфер, пропускаются. Сохраняются размеры viewport;
для кадров сцены выбирается штатный preset 1280×720 и отключаются helpers.
PNG использует фактическую client area: на проверенном Editor это 1276×716.

`/cutscene/open` загружает приватную копию сцены через штатный Import.
`/cutscene/seek` выбирает камеру оригинальным меню и перематывает оригинальными
командами Restart/Next Frame. Шаг текущего Editor — 33 мс; API возвращает
`requestedTimeMs`, `actualTimeMs` и исходный статус редактора. Readback индикатора
имеет точность 10 мс. Большая перемотка
может занимать время; запросы к одному worker выполняются последовательно.
Короткое имя камеры принимается только при единственном совпадении. Иначе
нужно точное уникальное имя из native Camera menu; неоднозначный выбор отклоняется.

Чёрные и однотонные кадры завершаются `status=FAILED` (HTTP 422), сохраняя PNG
для диагностики. `allow_empty:true` разрешает вернуть такой артефакт, но не делает
его проверенным кадром. `requestedCutsceneFrameVerified=true` требует загрузки
сцены, подтверждения камеры/времени, совпадения viewport и изображения с деталями.
Оригинальная сцена и карта/мод сохраняются неизменными; ресурсы берутся из
контекста переданного шаблона и его установленных зависимостей.

Пример последовательных POST-запросов с заголовком `X-SC2-Token`:

```text
/cutscene/open   {"template":"D:\\MyMod.SC2Mod","scene":"D:\\Intro.SC2Cutscene"}
/cutscene/seek   {"camera":"Front Formation Camera","time_ms":990}
/render/capture  {}
```

Также `/render/capture` принимает `camera` и `time_ms`, чтобы выбрать кадр и сразу
получить PNG-артефакт. MCP `sc2_capture_frame` возвращает изображение прямо клиенту.

## Экспорт MP4

`POST /cutscene/export` или MCP `sc2_export_video` использует кадры оригинального
рендера выбранной камеры. FFmpeg кодирует H.264/yuv420p MP4 с `faststart`, CRF 18.
Это **видео без звука**; звук из SC2 пока не экспортируется. FFmpeg и ffprobe нужны
на PATH; альтернативно задайте `SC2_FFMPEG` и `SC2_FFPROBE`. Они не входят в ZIP.

Можно сразу загрузить сцену, автоматически запустить скрытый Editor и выгрузить
всю сцену. Без `end_ms` конец берётся из первого включённого Director End Scene;
если его нет — из длительности элементов (`durationSource=authoredElements`).
При неизвестной длительности передайте `end_ms` явно.

```json
{"template":"D:\\MyMod.SC2Mod","scene":"D:\\Intro.SC2Cutscene",
 "camera":"Front Formation Camera","output":"D:\\Intro.mp4"}
```

Для уже открытой сцены — выбранный диапазон (конец не включается):

```json
{"camera":"Top","start_ms":990,"end_ms":1980,"fps":30,
 "output":"D:\\SelectedRange.mp4"}
```

`fps` — целое 1…60, по умолчанию 30. Исходные моменты привязываются к штатной
сетке 33 мс. При FPS выше её частоты повторяются ближайшие исходные кадры;
это отражено в `repeatedSamples`. Число кадров — `ceil((end-start)*fps/1000)`;
длительность MP4 равна этому числу / FPS и может отличаться от диапазона менее
чем на один выходной кадр. `firstNativeTimeMs`/`lastNativeTimeMs` показывают
фактический диапазон исходных моментов. Поддержан таймлайн до 600 000 мс.

Перемотка выполняется последовательно, без Restart для каждого кадра. Запись
может занимать дольше длительности ролика. API экспортирует синхронно, поэтому
HTTP-клиенту нужен достаточный timeout; параллельно можно читать прогресс:

```text
GET  /cutscene/export/status
POST /cutscene/export/cancel  {"job_id":"ID из progress"}
```

Оба запроса требуют `X-SC2-Token`. Отмена проверяется между кадрами и перед
публикацией файла; целевой файл при отмене не появляется. Существующий MP4
сохраняется, если явно не передан `overwrite:true`. Финальный файл публикуется
атомарно после проверки числа кадров/FPS/длительности, полного декодирования
ролика и проверки деталей в декодированном кадре.

Чёрные кадры внутри видео сохраняются, чтобы не вырезать авторские fade-переходы.
Полностью пустой диапазон отклоняется. Наблюдения рабочего стола входят в отчёт.
Кадры PNG по умолчанию временные; `keep_frames:true` оставляет их для диагностики.
`frameManifest` содержит таймкоды, HWND источника, статистику и хэши исходных кадров.
MP4 возвращается как `video/mp4` артефакт и скачивается по `/artifacts/<id>`.

Исходники находятся в ветке `main` приватного
[репозитория SC2NativeToolkit](https://github.com/VoVanRusLvSC2/SC2NativeToolkit/tree/main):
`app/sc2native/video.py`, `src/cutscene_bridge.inc`, HTTP/MCP-модули и тесты.

## Требования

Windows x64, установленный SC2 Editor по пути
`C:\Program Files (x86)\StarCraft II\Support64\SC2Editor_x64.exe`, настоящие
зависимости карты/мода. Текущий нативный адаптер рассчитан на проверенную сборку
Editor **5.0.17.98310**, использующую D3D9. Нужен интерактивный сеанс Windows.

## Готовые программы

`SC2NativeAPI.exe` — локальный HTTP API, без консоли.
`SC2NativeMCP.exe` — MCP stdio, без консоли при запуске клиентом с pipe handles.
Запуск Editor отложен до первой операции с картой/модом.

HTTP по умолчанию: `http://127.0.0.1:8765`.
`api-data/api-info.json` рядом с EXE содержит адрес и случайный token.
Для POST и скачивания артефактов нужен заголовок `X-SC2-Token`.
Операции редактора сериализованы; повторный запрос во время работы получает отказ.
Для больших карт задавайте timeout клиента не менее 1200 секунд.

## HTTP API

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Состояние и занятость |
| GET | `/modules` | Реализованные возможности |
| POST | `/editor/start` | `{"template":"D:\\MyMod.SC2Mod"}` — скрытый запуск |
| POST | `/open` | `{"map":"D:\\MyMap.SC2Map"}` — открыть частную копию |
| POST | `/convert` | XML + шаблон → оригинальный Galaxy + compile по умолчанию |
| POST | `/triggers/compile` | Проверить текущие триггеры штатным компилятором |
| POST | `/galaxy/export` | Экспорт последнего нативного результата |
| GET | `/artifacts/<id>` | Скачать точные байты артефакта |
| POST | `/editor/diagnostics` | Прочитать Messages/Console |
| POST | `/cutscene/open` | Открыть нативный Cutscene module |
| POST | `/render/capture` | Получить PNG следующего представленного viewport |
| POST | `/shutdown` | Закрыть API и принадлежащий ему Editor |

Пример обычной проверки существующего мода:

```powershell
$api = Get-Content '.\api-data\api-info.json' -Raw | ConvertFrom-Json
$h = @{'X-SC2-Token'=$api.token}
function Call-SC2($route,$value) {
  $body=[Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 12))
  Invoke-RestMethod ($api.url+$route) -Method Post -Headers $h `
    -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 1200
}
Call-SC2 '/editor/start' @{template='D:\MyMod.SC2Mod'}
$checked=Call-SC2 '/triggers/compile' @{scope='library:810D62ED'}
$export=Call-SC2 '/galaxy/export' @{output='D:\Native.galaxy'}
```

Без `scope` программа определяет единственную авторскую библиотеку либо mapRoot.
При неоднозначных строках укажите `context_label` — точную корневую категорию
или имя авторской библиотеки. Ошибки компилятора находятся в `diagnostics.compilerErrors`,
журналы — в `diagnostics.editorLog`. Непрочитанный журнал имеет `clear=null`.
Старые сообщения не скрываются и не смешиваются с результатом компиляции.

Для нового XML:

```json
{"template":"D:\\MyMod.SC2Mod","triggers_file":"D:\\Triggers.xml",
 "scope":"library:810D62ED","compile":true}
```

Вместо `triggers_file` можно передать полную UTF-8 строку `triggers_xml`.
Без обоих полей `/convert` извлекает существующий Triggers из шаблона.
Шаблон сохраняет контекст, локализацию и реальные зависимости.
Для экспорта существующий файл требует явного `overwrite:true`.

Результаты содержат исходные нативные отчёты, hashes, количество ошибок и наблюдения
пользовательского desktop. Логический focus внутри приватного desktop допустим:
он нужен штатному Editor для выбора правильной панели и не переключает desktop
пользователя. События активации приватного desktop учитываются отдельно.

## MCP

Пример конфигурации stdio-клиента:

```json
{"mcpServers":{"sc2-native":{"command":"D:\\SC2NativeToolkit\\SC2NativeMCP.exe",
 "args":["--work","D:\\SC2NativeToolkit-data"]}}}
```

Инструменты: `sc2_editor_start`, `sc2_open_document`, `sc2_convert_xml`,
`sc2_compile_all`, `sc2_export_galaxy`, `sc2_diagnostics`, `sc2_cutscene_open`,
`sc2_cutscene_seek`, `sc2_capture_frame`, `sc2_export_video`, `sc2_modules`. Кадр возвращается как MCP image и PNG-артефакт.
Большой Galaxy не вкладывается в текст MCP: используйте отдельный экспорт.
При закрытии stdio-соединения принадлежащий серверу Editor завершается.

## Сборка

Python 3.11+, Visual Studio C++ x64 Build Tools и Windows SDK.
MSVC/SDK определяются через `vswhere`; персональные пути в сборке не нужны.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\install-mpqcli.ps1
.\build.ps1
.\package.ps1 -Python .\.venv\Scripts\python.exe
.venv\Scripts\python.exe -m unittest discover -s tests
```

`mpqcli` закреплён на v0.10.0 и проверяется по SHA-256. В исходники его EXE не
включён; сборка/релиз используют локальный бинарник. См. `THIRD_PARTY.txt`.

Живой тест с собственным шаблоном:

```powershell
.venv\Scripts\python.exe tests\live_smoke.py --package `
  --template 'D:\MyMod.SC2Mod' --scope library:810D62ED --work 'D:\FreshTest'
```

Тесты без Editor проверяют протокол, файлы и защиту экспорта. Только live-тест
подтверждает штатную генерацию/компиляцию; это различие сохраняется в отчётах.

## Устройство проекта

`src/` — C++ DLL, launcher, IPC controller, D3D9 renderer/capture.
`app/sc2native/` — session, diagnostics, artifacts, HTTP, MCP, capabilities.
`app/native_xml_oracle.py` — проверенный нативный XML pipeline.
`vendor/minhook/` — закреплённые исходники MinHook и лицензия.
`tests/` — автоматические и opt-in live проверки; пользовательские файлы игнорируются.

Исходный Editor на диске, пользовательские моды и зависимости не патчатся.
Windows Job Object связывает жизнь скрытого Editor с владельцем API/MCP.

Технические ссылки: [D3D9 GetRenderTargetData](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-getrendertargetdata),
[MCP stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

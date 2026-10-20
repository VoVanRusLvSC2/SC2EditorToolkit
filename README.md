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
| Cutscene | Адаптер открытия оригинального модуля; база для дальнейшего управления сценой |
| MCP | Отдельный stdio EXE, инструменты редактора/экспорта/диагностик/рендера |

Генератор и компилятор — **оригинальные**, работающие внутри установленного Editor.
Собственного Galaxy-генератора здесь нет. Внутренние GUI-окна существуют только
на приватном desktop; техническое окно графического потока невидимо.

## Границы рендера

Кадр берётся непосредственно перед `Present`, при необходимости с resolve MSAA,
копированием render target в system memory и PNG-кодированием через Windows WIC.
Это текущий представляемый viewport редактора. Автоматический выбор конкретного
ролика, загрузка его таймлайна, установка времени, выбор камеры и отбор нужного
viewport ещё **не реализованы**. Поэтому API не выдаёт произвольный viewport за
проверенный кадр заданной катсцены. Эти операции предусмотрены отдельным модулем,
без изменений компилятора/экспорта/MCP транспорта.
Чёрный буфер помечается `emptyFrame=true`; `requestedCutsceneFrameVerified=false`
явно указывает, что кадр конкретного ролика ещё не подтверждён.

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
`sc2_capture_frame`, `sc2_modules`. Кадр возвращается как MCP image и PNG-артефакт.
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

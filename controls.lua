local mp = require "mp"
local options = { portrait_video = "" }
require("mp.options").read_options(options, "toutbien")
local portrait_video = options.portrait_video

local function quit()
    mp.commandv("quit", "0")
end

mp.add_forced_key_binding("q", "toutbien-quit", quit)
mp.add_forced_key_binding("Q", "toutbien-quit-uppercase", quit)
mp.add_forced_key_binding("ESC", "toutbien-quit-escape", quit)

local standby_overlay = mp.create_osd_overlay("ass-events")
standby_overlay.res_x = 1280
standby_overlay.res_y = 720

local colors = {
    idle = "4444EF",
    motion = "5EC522",
}
local circle = "m 12 0 b 19 0 24 5 24 12 b 24 19 19 24 12 24 b 5 24 0 19 0 12 b 0 5 5 0 12 0"

local portrait = true
local status, number = "hidden", ""

local function draw_standby()
    local color = colors[status]
    if not color then
        standby_overlay:remove()
        return
    end

    -- OSD coordinates stay in landscape even when mpv rotates the image.
    local dot_position = portrait and [[\pos(32,664)]] or [[\pos(32,26)]]
    standby_overlay.data = [[{\an7]] .. dot_position .. [[\bord0\shad0\1c&H]] ..
        color .. [[&\p1}]] .. circle .. [[{\p0}]]
    if not portrait and number:match("^[123]$") then
        local position = [[\an8\pos(640,430)]]
        standby_overlay.data = standby_overlay.data .. "\n" .. "{" .. position ..
            [[\fnObviously\fs102\b1\1c&H2113D6&\bord0\shad0}]] .. number
    end
    standby_overlay:update()
end

mp.register_script_message("toutbien-standby", function(new_status, new_number)
    status, number = new_status, new_number or ""
    draw_standby()
end)

local function is_standby(path)
    return path:match("[/\\]standby%.png$") ~= nil
end

local function is_product_video(path)
    return path:match("[/\\]productvideo%.mp4$") ~= nil
end

mp.add_hook("on_load", 50, function()
    local path = mp.get_property("path", "")
    if portrait and is_standby(path) then
        mp.set_property("stream-open-filename", portrait_video)
        mp.set_property_native("file-local-options/pause", true)
    elseif is_product_video(path) then
        if portrait then
            mp.set_property("stream-open-filename", portrait_video)
        end
        mp.set_property_native("file-local-options/pause", false)
    end
end)

local function set_orientation(use_portrait)
    if portrait == use_portrait then
        return
    end
    portrait = use_portrait
    mp.set_property_number("video-rotate", portrait and 270 or 0)
    local path = mp.get_property("path", "")
    if is_standby(path) or is_product_video(path) then
        mp.commandv("loadfile", path, "replace")
    end
    draw_standby()
end

for _, key in ipairs({"p", "P"}) do
    mp.add_forced_key_binding(key, "toutbien-portrait-" .. key, function()
        set_orientation(true)
    end)
end
for _, key in ipairs({"l", "L"}) do
    mp.add_forced_key_binding(key, "toutbien-landscape-" .. key, function()
        set_orientation(false)
    end)
end

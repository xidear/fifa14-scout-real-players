package com.zcode.jersey;

/** Static bridge between MainActivity and PanelService. */
final class PanelBus {
    private PanelBus() {}
    static volatile String quickName = null;
    static volatile boolean hide = false;
}
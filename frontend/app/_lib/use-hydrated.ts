"use client";
import { useSyncExternalStore } from "react";

const subscribe = () => () => {};
const client = () => true;
const server = () => false;

// Keep interactive controls disabled until their client-side handlers are attached.
export function useHydrated() {
  return useSyncExternalStore(subscribe, client, server);
}

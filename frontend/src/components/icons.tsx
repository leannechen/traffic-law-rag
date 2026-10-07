import type { ReactNode, SVGProps } from 'react'

type IconProps = Omit<SVGProps<SVGSVGElement>, 'children'> & { size?: number }

export function Icon({
  size = 16,
  strokeWidth = 2,
  children,
  ...rest
}: IconProps & { children?: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  )
}

const path = (d: string | string[]) =>
  function PathIcon(props: IconProps) {
    return (
      <Icon {...props}>
        {(Array.isArray(d) ? d : [d]).map((p) => (
          <path key={p} d={p} />
        ))}
      </Icon>
    )
  }

export const ArrowRightIcon = path(['M5 12h14', 'm12 5 7 7-7 7'])
export const MenuIcon = path(['M4 7h16', 'M4 12h16', 'M4 17h16'])
export const CloseIcon = path(['M6 6l12 12', 'M18 6 6 18'])
export const ChevronIcon = path('m9 6 6 6-6 6')
export const CheckIcon = path('M20 6 9 17l-5-5')
export const SpinnerIcon = path('M21 12a9 9 0 1 1-6.2-8.6')

export function StopIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" />
    </svg>
  )
}

export function InfoIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </Icon>
  )
}

export function AlertIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </Icon>
  )
}

export function ClockIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </Icon>
  )
}

export function SearchOffIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
      <path d="M8 11h6" />
    </Icon>
  )
}

export function SunIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </Icon>
  )
}

export function MoonIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </Icon>
  )
}

export function MonitorIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3" y="4" width="18" height="12" rx="0" />
      <path d="M8 20h8" />
      <path d="M12 16v4" />
    </Icon>
  )
}

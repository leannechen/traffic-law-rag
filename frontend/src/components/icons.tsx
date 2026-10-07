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

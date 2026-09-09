export const matrixScrollContentWidth = (
  tableWidth: number,
  containerWidth: number,
  clientWidth: number,
) => tableWidth + Math.max(0, containerWidth - clientWidth)
